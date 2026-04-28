"""
Week 2: Voice Agent - Whisper → Intent Classifier → TTS (End-to-end latency)
"""

import asyncio
import logging
import time
import numpy as np
from dataclasses import dataclass
from typing import Dict, List
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class PipelineMetrics:
    """Track end-to-end pipeline latencies"""
    request_id: str
    whisper_latency_ms: float
    classifier_latency_ms: float
    tts_latency_ms: float
    total_latency_ms: float
    error: str = None

class VoiceAgent:
    """Orchestrate Whisper → Classifier → TTS"""
    
    def __init__(self):
        logger.info("Initializing Voice Agent...")
        self.metrics: List[PipelineMetrics] = []
        self.errors = {"whisper": 0, "classifier": 0, "tts": 0}
    
    async def whisper_transcribe(self, audio_bytes: bytes, request_id: str) -> tuple:
        """Simulate Whisper transcription"""
        start = time.time()
        
        # Simulate processing
        audio_length_sec = len(audio_bytes) / (16000 * 2)  # Rough estimate
        simulated_latency = 100 + (audio_length_sec * 50)  # ms
        
        await asyncio.sleep(simulated_latency / 1000.0)
        
        latency_ms = (time.time() - start) * 1000
        text = f"Transcribed audio for {request_id}"
        
        return text, latency_ms
    
    async def classify_intent(self, text: str, request_id: str) -> tuple:
        """Simulate intent classification"""
        start = time.time()
        
        # Simulate classifier
        await asyncio.sleep(0.050)  # 50ms
        
        latency_ms = (time.time() - start) * 1000
        intent = "greeting"
        confidence = 0.95
        
        return intent, confidence, latency_ms
    
    async def tts_synthesize(self, text: str, request_id: str) -> tuple:
        """Simulate TTS synthesis"""
        start = time.time()
        
        # Simulate TTS
        words = len(text.split())
        simulated_latency = 50 + (words * 10)  # ms
        await asyncio.sleep(simulated_latency / 1000.0)
        
        latency_ms = (time.time() - start) * 1000
        audio_url = f"audio_{request_id}.wav"
        
        return audio_url, latency_ms
    
    async def process_request(self, audio_bytes: bytes, request_id: str) -> PipelineMetrics:
        """Process complete pipeline"""
        e2e_start = time.time()
        
        try:
            # Stage 1: Whisper
            text, whisper_lat = await self.whisper_transcribe(audio_bytes, request_id)
            
            # Stage 2: Intent Classification
            intent, confidence, classifier_lat = await self.classify_intent(text, request_id)
            
            # Stage 3: TTS
            audio_url, tts_lat = await self.tts_synthesize(text, request_id)
            
            e2e_latency = (time.time() - e2e_start) * 1000
            
            metrics = PipelineMetrics(
                request_id=request_id,
                whisper_latency_ms=whisper_lat,
                classifier_latency_ms=classifier_lat,
                tts_latency_ms=tts_lat,
                total_latency_ms=e2e_latency,
            )
            
            self.metrics.append(metrics)
            return metrics
        
        except Exception as e:
            logger.error(f"Pipeline error: {e}")
            self.errors["pipeline"] = self.errors.get("pipeline", 0) + 1
            return PipelineMetrics(
                request_id=request_id,
                whisper_latency_ms=0,
                classifier_latency_ms=0,
                tts_latency_ms=0,
                total_latency_ms=0,
                error=str(e)
            )
    
    async def simulate_concurrent_requests(self, num_requests: int = 10):
        """Simulate concurrent voice requests"""
        logger.info(f"🎤 Processing {num_requests} concurrent voice requests")
        logger.info("="*60)
        
        # Generate synthetic audio
        tasks = []
        for i in range(num_requests):
            audio_bytes = np.random.randint(0, 255, 16000 * 5, dtype=np.uint8).tobytes()
            task = self.process_request(audio_bytes, f"req_{i}")
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        
        # Print results
        logger.info("\n" + "="*60)
        logger.info("VOICE AGENT END-TO-END METRICS")
        logger.info("="*60)
        
        latencies = [m.total_latency_ms for m in results if m.error is None]
        whisper_lats = [m.whisper_latency_ms for m in results if m.error is None]
        classifier_lats = [m.classifier_latency_ms for m in results if m.error is None]
        tts_lats = [m.tts_latency_ms for m in results if m.error is None]
        
        logger.info("\nEnd-to-End Latency:")
        logger.info(f"  p50: {np.percentile(latencies, 50):.1f}ms")
        logger.info(f"  p95: {np.percentile(latencies, 95):.1f}ms")
        logger.info(f"  p99: {np.percentile(latencies, 99):.1f}ms")
        
        logger.info("\nComponent Breakdown:")
        logger.info(f"  Whisper avg: {np.mean(whisper_lats):.1f}ms")
        logger.info(f"  Classifier avg: {np.mean(classifier_lats):.1f}ms")
        logger.info(f"  TTS avg: {np.mean(tts_lats):.1f}ms")
        logger.info(f"  Total avg: {np.mean(latencies):.1f}ms")
        
        logger.info(f"\nRequests processed: {len([m for m in results if m.error is None])}")
        logger.info(f"Errors: {len([m for m in results if m.error is not None])}")
        logger.info("="*60)
        
        return results

async def main():
    agent = VoiceAgent()
    await agent.simulate_concurrent_requests(num_requests=20)

if __name__ == "__main__":
    asyncio.run(main())
