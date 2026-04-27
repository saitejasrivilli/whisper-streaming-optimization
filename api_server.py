"""
FastAPI server for streaming Whisper inference.

Exposes:
- /transcribe/stream: WebSocket for streaming audio + results
- /health: System health + metrics
- /metrics: Detailed performance metrics

Designed for:
- Real-time transcription of voice streams
- Concurrent clients (each gets independent stream)
- p99 latency monitoring
"""

import asyncio
import logging
import time
import numpy as np
from typing import AsyncGenerator
import json
from collections import defaultdict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Import our optimized engine
import sys
sys.path.insert(0, "/home/claude/whisper_streaming_optimization")
from main import StreamingWhisperOptimized

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# Global State
# ============================================================================

app = FastAPI(title="Streaming Whisper API", version="1.0.0")

# CORS for web clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize engine once at startup
whisper_engine: Optional[StreamingWhisperOptimized] = None
client_metrics = defaultdict(lambda: {
    "requests": 0,
    "errors": 0,
    "total_latency_ms": 0,
    "first_token_latencies": [],
})


@app.on_event("startup")
async def startup():
    """Initialize Whisper engine on startup"""
    global whisper_engine
    logger.info("🚀 Initializing Whisper streaming engine...")
    whisper_engine = StreamingWhisperOptimized(
        model_name="base",
        num_gpus=3,
        buffer_max_wait_ms=50,
        profile=False,
    )
    logger.info("✅ Engine ready")


@app.on_event("shutdown")
async def shutdown():
    """Cleanup"""
    logger.info("Shutting down...")


# ============================================================================
# Endpoints
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "engine": "ready" if whisper_engine else "not_initialized",
        "gpu_count": 3,
    }


@app.get("/metrics")
async def get_metrics():
    """Get detailed performance metrics"""
    if not whisper_engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    
    metrics = whisper_engine.get_metrics()
    
    return {
        "engine_metrics": metrics,
        "client_metrics": {
            client_id: {
                "requests": data["requests"],
                "errors": data["errors"],
                "avg_latency_ms": data["total_latency_ms"] / max(1, data["requests"]),
                "first_token_p99_ms": np.percentile(data["first_token_latencies"], 99) if data["first_token_latencies"] else 0,
            }
            for client_id, data in client_metrics.items()
        },
    }


@app.websocket("/transcribe/stream")
async def websocket_transcribe(websocket: WebSocket):
    """
    WebSocket endpoint for streaming transcription.
    
    Protocol:
    1. Client connects
    2. Client sends audio frames as binary messages (PCM 16-bit, 16kHz)
    3. Server transcribes and sends results as JSON messages
    4. Client sends empty frame to signal end of stream
    5. Connection closes
    
    Example client:
    ```python
    import asyncio
    import websockets
    import numpy as np
    
    async def send_audio():
        uri = "ws://localhost:8000/transcribe/stream"
        async with websockets.connect(uri) as websocket:
            # Send 100ms of audio (1600 samples @ 16kHz)
            audio = np.random.randn(1600).astype(np.float32)
            await websocket.send(audio.tobytes())
            
            # Receive result
            result = await websocket.recv()
            print(json.loads(result))
    ```
    """
    client_id = None
    
    await websocket.accept()
    logger.info("📱 Client connected")
    
    try:
        client_id = f"client_{int(time.time() * 1000)}"
        client_metrics[client_id]["requests"] = 0
        client_metrics[client_id]["errors"] = 0
        
        # Generate audio chunks from WebSocket messages
        async def receive_audio_chunks() -> AsyncGenerator[np.ndarray, None]:
            """Receive audio frames from WebSocket"""
            while True:
                try:
                    data = await websocket.receive_bytes()
                    if not data:  # Empty frame signals end
                        break
                    # Convert bytes to float32 audio
                    audio = np.frombuffer(data, dtype=np.float32)
                    yield audio
                except WebSocketDisconnect:
                    logger.info(f"Client {client_id} disconnected")
                    break
                except Exception as e:
                    logger.error(f"Error receiving audio: {e}")
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "error": str(e),
                    }))
                    break
        
        # Process stream
        async for result in whisper_engine.process_stream(
            receive_audio_chunks(),
            client_id
        ):
            # Send result back to client
            if result["type"] == "result":
                client_metrics[client_id]["requests"] += 1
                client_metrics[client_id]["total_latency_ms"] += result["latency_ms"]
                client_metrics[client_id]["first_token_latencies"].append(result["latency_ms"])
                
                await websocket.send_text(json.dumps({
                    "type": "result",
                    "text": result["text"],
                    "latency_ms": result["latency_ms"],
                    "utterance": result["utterance"],
                }))
                
            elif result["type"] == "metrics":
                await websocket.send_text(json.dumps({
                    "type": "metrics",
                    "e2e_latency_ms": result["e2e_latency_ms"],
                    "utterances": result["utterances"],
                }))
            
            elif result["type"] == "error":
                client_metrics[client_id]["errors"] += 1
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "error": result["error"],
                }))
    
    except WebSocketDisconnect:
        logger.info(f"Client {client_id} disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_text(json.dumps({
                "type": "error",
                "error": str(e),
            }))
        except:
            pass
    finally:
        try:
            await websocket.close()
        except:
            pass
        logger.info(f"Client {client_id} session ended")


# ============================================================================
# Utility: Simulate client for testing
# ============================================================================

@app.get("/test/generate-client")
async def generate_test_client():
    """
    Returns Python code for a test client.
    Usage:
    1. GET /test/generate-client
    2. Copy response and run as test_client.py
    3. python test_client.py
    """
    return {
        "message": "See code in response body",
        "code": """
import asyncio
import websockets
import numpy as np
import json
import time

async def test_streaming_transcription():
    uri = "ws://localhost:8000/transcribe/stream"
    
    print("Connecting to streaming server...")
    async with websockets.connect(uri) as websocket:
        # Simulate streaming audio (5 seconds)
        sample_rate = 16000
        duration_sec = 5.0
        total_samples = int(sample_rate * duration_sec)
        
        # Generate synthetic audio (white noise)
        audio = np.random.randn(total_samples).astype(np.float32) * 0.05
        
        # Send in 100ms chunks with simulated network jitter
        chunk_size_samples = sample_rate // 10
        samples_sent = 0
        
        print("Sending audio stream...")
        while samples_sent < total_samples:
            # Simulate jitter
            jitter = np.random.uniform(-0.01, 0.01)
            await asyncio.sleep(0.1 + jitter)
            
            chunk_end = min(samples_sent + chunk_size_samples, total_samples)
            chunk = audio[samples_sent:chunk_end].tobytes()
            await websocket.send(chunk)
            samples_sent = chunk_end
        
        # Send empty frame to signal end
        await websocket.send(b'')
        
        # Receive results
        print("Receiving transcriptions...")
        try:
            while True:
                msg = await websocket.recv()
                result = json.loads(msg)
                if result["type"] == "result":
                    print(f"  Utterance {result['utterance']}: {result['text'][:50]}... "
                          f"(latency: {result['latency_ms']:.1f}ms)")
                elif result["type"] == "metrics":
                    print(f"  Complete. E2E latency: {result['e2e_latency_ms']:.1f}ms")
                    break
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_streaming_transcription())
"""
    }


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    import sys
    
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    
    logger.info(f"🌟 Starting API server on port {port}")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info",
    )
