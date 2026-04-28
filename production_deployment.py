"""
Week 3: Production Deployment - Docker/K8s monitoring & load testing
"""

import asyncio
import logging
import time
import json
import numpy as np
from dataclasses import dataclass
from typing import Dict, List
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class DeploymentMetrics:
    """Track production deployment metrics"""
    timestamp: str
    concurrent_requests: int
    qps: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    error_rate_pct: float
    cpu_usage_pct: float
    memory_usage_mb: float
    gpu_utilization_pct: float

class ProductionMonitor:
    """Monitor production deployment"""
    
    def __init__(self):
        logger.info("Initializing Production Monitor...")
        self.metrics_history: List[DeploymentMetrics] = []
        self.alerts = []
        self.thresholds = {
            "p99_latency_ms": 300,
            "error_rate_pct": 1.0,
            "cpu_usage_pct": 85,
            "gpu_utilization_pct": 90,
        }
    
    async def simulate_request(self, request_id: str) -> float:
        """Simulate a single request"""
        # Random latency between 50-300ms
        latency_ms = np.random.normal(150, 50)
        latency_ms = max(50, min(300, latency_ms))  # Clamp
        
        await asyncio.sleep(latency_ms / 1000.0)
        return latency_ms
    
    async def run_load_test(self, initial_qps: int = 100, spike_qps: int = 1000, duration_sec: int = 60):
        """Run production load test"""
        logger.info(f"🚀 Starting load test: {initial_qps} → {spike_qps} QPS")
        logger.info("="*60)
        
        start_time = time.time()
        all_latencies = []
        errors = 0
        total_requests = 0
        
        while time.time() - start_time < duration_sec:
            elapsed = time.time() - start_time
            
            # Gradually spike after 30 seconds
            if elapsed < 30:
                current_qps = initial_qps
                concurrent = min(int(initial_qps / 10), 50)
            else:
                progress = (elapsed - 30) / 30.0
                current_qps = int(initial_qps + (spike_qps - initial_qps) * progress)
                concurrent = min(int(current_qps / 10), 200)
            
            # Create concurrent requests
            tasks = []
            for i in range(concurrent):
                task = self.simulate_request(f"req_{total_requests}_{i}")
                tasks.append(task)
            
            try:
                latencies = await asyncio.gather(*tasks, return_exceptions=True)
                for lat in latencies:
                    if isinstance(lat, float):
                        all_latencies.append(lat)
                        total_requests += 1
                    else:
                        errors += 1
            except Exception as e:
                logger.error(f"Request error: {e}")
                errors += 1
            
            # Record metrics every 10 seconds
            if int(elapsed) % 10 == 0:
                if all_latencies:
                    metrics = DeploymentMetrics(
                        timestamp=datetime.now().isoformat(),
                        concurrent_requests=concurrent,
                        qps=total_requests / elapsed,
                        p50_latency_ms=np.percentile(all_latencies, 50),
                        p95_latency_ms=np.percentile(all_latencies, 95),
                        p99_latency_ms=np.percentile(all_latencies, 99),
                        error_rate_pct=(errors / max(1, total_requests)) * 100,
                        cpu_usage_pct=np.random.uniform(30, 85),  # Simulated
                        memory_usage_mb=np.random.uniform(1000, 4000),  # Simulated
                        gpu_utilization_pct=np.random.uniform(40, 95),  # Simulated
                    )
                    self.metrics_history.append(metrics)
                    
                    # Check thresholds
                    self._check_alerts(metrics)
            
            await asyncio.sleep(0.1)  # Small delay
        
        # Print summary
        self._print_summary(all_latencies, errors, total_requests)
    
    def _check_alerts(self, metrics: DeploymentMetrics):
        """Check if metrics exceed thresholds"""
        if metrics.p99_latency_ms > self.thresholds["p99_latency_ms"]:
            alert = f"⚠️  High p99 latency: {metrics.p99_latency_ms:.0f}ms"
            logger.warning(alert)
            self.alerts.append(alert)
        
        if metrics.error_rate_pct > self.thresholds["error_rate_pct"]:
            alert = f"⚠️  High error rate: {metrics.error_rate_pct:.1f}%"
            logger.warning(alert)
            self.alerts.append(alert)
        
        if metrics.gpu_utilization_pct > self.thresholds["gpu_utilization_pct"]:
            alert = f"⚠️  High GPU utilization: {metrics.gpu_utilization_pct:.0f}%"
            logger.warning(alert)
            self.alerts.append(alert)
    
    def _print_summary(self, latencies: List[float], errors: int, total_requests: int):
        """Print load test summary"""
        logger.info("\n" + "="*60)
        logger.info("PRODUCTION LOAD TEST SUMMARY")
        logger.info("="*60)
        
        if latencies:
            logger.info(f"\nLatency Distribution:")
            logger.info(f"  p50:   {np.percentile(latencies, 50):7.1f}ms")
            logger.info(f"  p95:   {np.percentile(latencies, 95):7.1f}ms")
            logger.info(f"  p99:   {np.percentile(latencies, 99):7.1f}ms")
            logger.info(f"  p99.9: {np.percentile(latencies, 99.9):7.1f}ms")
            logger.info(f"  mean:  {np.mean(latencies):7.1f}ms")
            logger.info(f"  max:   {np.max(latencies):7.1f}ms")
        
        error_rate = (errors / max(1, total_requests)) * 100
        logger.info(f"\nReliability:")
        logger.info(f"  Total requests: {total_requests}")
        logger.info(f"  Errors: {errors}")
        logger.info(f"  Error rate: {error_rate:.2f}%")
        
        if self.metrics_history:
            final_qps = self.metrics_history[-1].qps
            logger.info(f"\nThroughput:")
            logger.info(f"  Final QPS: {final_qps:.1f}")
        
        logger.info(f"\nAlerts Triggered: {len(self.alerts)}")
        for alert in self.alerts[-5:]:  # Show last 5
            logger.info(f"  {alert}")
        
        logger.info("="*60)
        
        # Export metrics to JSON
        self._export_metrics()
    
    def _export_metrics(self):
        """Export metrics to JSON for dashboard"""
        metrics_dict = [
            {
                "timestamp": m.timestamp,
                "concurrent": m.concurrent_requests,
                "qps": m.qps,
                "p50": m.p50_latency_ms,
                "p95": m.p95_latency_ms,
                "p99": m.p99_latency_ms,
                "error_rate": m.error_rate_pct,
                "cpu": m.cpu_usage_pct,
                "memory_mb": m.memory_usage_mb,
                "gpu": m.gpu_utilization_pct,
            }
            for m in self.metrics_history
        ]
        
        with open("production_metrics.json", "w") as f:
            json.dump(metrics_dict, f, indent=2)
        
        logger.info("✓ Metrics exported to production_metrics.json")

async def main():
    monitor = ProductionMonitor()
    # Load test: 100 QPS → 1000 QPS spike
    await monitor.run_load_test(initial_qps=100, spike_qps=1000, duration_sec=60)

if __name__ == "__main__":
    asyncio.run(main())
