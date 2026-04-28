"""
Week 1: TTS Optimization - Real batching scheduler with p50/p95/p99 metrics
"""

import asyncio
import logging
import time
import numpy as np
from dataclasses import dataclass
from typing import List, Dict
import torch

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class BatchMetrics:
    """Track latencies per batch size"""
    batch_size: int
    latencies: List[float]
    
    def get_percentiles(self):
        if not self.latencies:
            return {}
        return {
            "p50": np.percentile(self.latencies, 50),
            "p95": np.percentile(self.latencies, 95),
            "p99": np.percentile(self.latencies, 99),
            "mean": np.mean(self.latencies),
            "max": np.max(self.latencies),
        }

class BatchingScheduler:
    """Intelligent batching for TTS"""
    
    def __init__(self, max_batch_size: int = 32, max_wait_ms: int = 50):
        self.max_batch_size = max_batch_size
        self.max_wait_ms = max_wait_ms
        self.queue = asyncio.Queue()
        self.metrics_by_batch = {i: BatchMetrics(i, []) for i in range(1, max_batch_size + 1)}
        self.profile_data = {}
    
    async def add_request(self, request_id: str, text: str):
        """Add request to queue"""
        await self.queue.put((request_id, text, time.time()))
    
    async def get_batch(self) -> tuple:
        """Get batch based on size or timeout"""
        batch = []
        start_time = time.time()
        
        while len(batch) < self.max_batch_size:
            try:
                # Wait for max_wait_ms or until batch full
                wait_remaining = (self.max_wait_ms / 1000.0) - (time.time() - start_time)
                if wait_remaining <= 0:
                    break
                
                item = await asyncio.wait_for(self.queue.get(), timeout=wait_remaining)
                batch.append(item)
            except asyncio.TimeoutError:
                break
        
        return batch
    
    def profile_batch(self, batch_size: int, latency_ms: float):
        """Record batch performance"""
        if batch_size in self.metrics_by_batch:
            self.metrics_by_batch[batch_size].latencies.append(latency_ms)

class TTSOptimizer:
    """TTS with GPU profiling"""
    
    def __init__(self):
        logger.info("Initializing TTS Optimizer...")
        self.batch_scheduler = BatchingScheduler(max_batch_size=32, max_wait_ms=50)
        self.gpu_available = torch.cuda.is_available()
        if self.gpu_available:
            logger.info(f"GPU available: {torch.cuda.get_device_name(0)}")
        
    async def synthesize_batch(self, batch: List[tuple]) -> Dict:
        """Synthesize audio for batch of texts"""
        if not batch:
            return {"error": "empty_batch"}
        
        batch_size = len(batch)
        start = time.time()
        
        # Simulate TTS processing (actual would use Tacotron2/FastPitch)
        # Latency increases with batch size (GPU batching efficiency)
        base_latency = 50  # ms for single request
        batch_overhead = 2 * np.log(batch_size)  # diminishing returns
        simulated_latency = base_latency + batch_overhead
        
        await asyncio.sleep(simulated_latency / 1000.0)
        
        latency_ms = (time.time() - start) * 1000
        self.batch_scheduler.profile_batch(batch_size, latency_ms)
        
        return {
            "batch_size": batch_size,
            "latency_ms": latency_ms,
            "audio_files": [f"audio_{req_id}.wav" for req_id, _, _ in batch],
        }
    
    async def run_profiling(self, num_requests: int = 100):
        """Profile different batch sizes"""
        logger.info(f"🔍 Profiling TTS with {num_requests} requests")
        logger.info("="*60)
        
        # Generate requests
        async def generate_requests():
            for i in range(num_requests):
                text = f"This is test request number {i}. " * 3
                await self.batch_scheduler.add_request(f"req_{i}", text)
                await asyncio.sleep(0.01)  # Simulate request arrival
        
        # Process batches
        async def process_batches():
            processed = 0
            while processed < num_requests:
                batch = await self.batch_scheduler.get_batch()
                if batch:
                    result = await self.synthesize_batch(batch)
                    processed += len(batch)
                    logger.info(f"  Batch {result['batch_size']}: {result['latency_ms']:.1f}ms")
        
        # Run concurrently
        await asyncio.gather(
            generate_requests(),
            process_batches(),
        )
        
        # Print results
        logger.info("\n" + "="*60)
        logger.info("TTS BATCHING PROFILING RESULTS")
        logger.info("="*60)
        
        for batch_size in sorted(self.batch_scheduler.metrics_by_batch.keys()):
            metrics = self.batch_scheduler.metrics_by_batch[batch_size]
            if metrics.latencies:
                percentiles = metrics.get_percentiles()
                logger.info(f"\nBatch size {batch_size:2d}:")
                logger.info(f"  p50: {percentiles['p50']:7.1f}ms")
                logger.info(f"  p95: {percentiles['p95']:7.1f}ms")
                logger.info(f"  p99: {percentiles['p99']:7.1f}ms")
                logger.info(f"  mean: {percentiles['mean']:7.1f}ms")
                logger.info(f"  samples: {len(metrics.latencies)}")
        
        logger.info("="*60)

async def main():
    optimizer = TTSOptimizer()
    await optimizer.run_profiling(num_requests=100)

if __name__ == "__main__":
    asyncio.run(main())
