import asyncio
import logging
import time
import numpy as np
import torch
import whisper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SimpleWhisper:
    def __init__(self):
        logger.info("Loading Whisper base model...")
        self.model = whisper.load_model("base")
        logger.info("✓ Model loaded")
    
    def transcribe(self, audio_np):
        """Transcribe audio"""
        try:
            result = self.model.transcribe(audio_np, language="en", verbose=False)
            return result.get("text", "")
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return f"Error: {str(e)[:30]}"

async def test_benchmark():
    """Simple benchmark"""
    logger.info("🚀 Starting Whisper Streaming Benchmark")
    logger.info("="*60)
    
    engine = SimpleWhisper()
    latencies = []
    
    # Generate 30 seconds of audio (enough for Whisper)
    sample_rate = 16000
    duration_sec = 10  # 10 seconds
    total_samples = sample_rate * duration_sec
    
    logger.info(f"Generating {duration_sec}s test audio ({total_samples} samples)...")
    audio_full = np.random.randn(total_samples).astype(np.float32) * 0.05
    
    # Process in chunks but transcribe full audio
    logger.info("Processing audio...")
    for i in range(3):
        start = time.time()
        text = await asyncio.to_thread(engine.transcribe, audio_full)
        latency_ms = (time.time() - start) * 1000
        latencies.append(latency_ms)
        logger.info(f"  Request {i+1}: {text[:40]}... ({latency_ms:.1f}ms)")
    
    # Summary
    logger.info("\n" + "="*60)
    logger.info("PERFORMANCE SUMMARY")
    logger.info("="*60)
    
    p50 = np.percentile(latencies, 50)
    p99 = np.percentile(latencies, 99) if len(latencies) > 1 else latencies[0]
    p999 = np.percentile(latencies, 99.9) if len(latencies) > 2 else latencies[-1]
    avg = np.mean(latencies)
    
    logger.info(f"Requests: {len(latencies)}")
    logger.info(f"p50 latency: {p50:.1f}ms")
    logger.info(f"p99 latency: {p99:.1f}ms")
    logger.info(f"p99.9 latency: {p999:.1f}ms")
    logger.info(f"Average latency: {avg:.1f}ms")
    logger.info("="*60)
    logger.info("✓ Benchmark complete!")

if __name__ == "__main__":
    asyncio.run(test_benchmark())
