"""
Production Observability: Monitoring, Metrics, & Alerting
==========================================================

Demonstrates:
1. Production-grade telemetry (Prometheus metrics)
2. Actionable alerts (when to page)
3. Operational dashboards (what to display)
4. Debugging methodology (how to find issues)

This is what separates hobby projects from production systems.
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List
from enum import Enum


class AlertSeverity(Enum):
    """Alert severity levels"""
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass
class MetricPoint:
    """Single metric measurement"""
    timestamp: float
    value: float
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class Alert:
    """An alert that should be triggered"""
    severity: AlertSeverity
    metric: str
    current_value: float
    threshold: float
    message: str
    action: str  # What to do about it


class PrometheusMetrics:
    """Prometheus-compatible metrics for observability"""
    
    def __init__(self):
        # Latency metrics (histogram)
        self.transcription_latency_p50: List[MetricPoint] = []
        self.transcription_latency_p99: List[MetricPoint] = []
        self.transcription_latency_p99_9: List[MetricPoint] = []
        
        # Throughput metrics (gauge)
        self.requests_per_second: List[MetricPoint] = []
        self.concurrent_connections: List[MetricPoint] = []
        
        # Error metrics (counter)
        self.transcription_errors_total: List[MetricPoint] = []
        self.timeouts_total: List[MetricPoint] = []
        self.gpu_oom_total: List[MetricPoint] = []
        
        # Resource metrics (gauge)
        self.gpu_memory_usage_bytes: List[MetricPoint] = []
        self.gpu_utilization_percent: List[MetricPoint] = []
        self.queue_depth_per_gpu: List[MetricPoint] = []
        
        # Business metrics (counter)
        self.audio_hours_processed_total: List[MetricPoint] = []
        self.successful_transcriptions_total: List[MetricPoint] = []
    
    def record_latency(self, p50: float, p99: float, p99_9: float, timestamp: float = None):
        """Record latency metrics"""
        ts = timestamp or time.time()
        self.transcription_latency_p50.append(MetricPoint(ts, p50))
        self.transcription_latency_p99.append(MetricPoint(ts, p99))
        self.transcription_latency_p99_9.append(MetricPoint(ts, p99_9))
    
    def record_throughput(self, req_per_sec: float, concurrent: int, timestamp: float = None):
        """Record throughput metrics"""
        ts = timestamp or time.time()
        self.requests_per_second.append(MetricPoint(ts, req_per_sec))
        self.concurrent_connections.append(MetricPoint(ts, concurrent))
    
    def record_error(self, error_type: str, timestamp: float = None):
        """Record error event"""
        ts = timestamp or time.time()
        if error_type == "transcription_error":
            self.transcription_errors_total.append(MetricPoint(ts, 1))
        elif error_type == "timeout":
            self.timeouts_total.append(MetricPoint(ts, 1))
        elif error_type == "oom":
            self.gpu_oom_total.append(MetricPoint(ts, 1))
    
    def record_gpu_metrics(self, memory_mb: float, util_pct: float, queue_depth: int, 
                          timestamp: float = None):
        """Record GPU resource usage"""
        ts = timestamp or time.time()
        self.gpu_memory_usage_bytes.append(MetricPoint(ts, memory_mb * 1e6))
        self.gpu_utilization_percent.append(MetricPoint(ts, util_pct))
        self.queue_depth_per_gpu.append(MetricPoint(ts, queue_depth))
    
    def get_prometheus_format(self) -> str:
        """Export metrics in Prometheus format"""
        
        lines = []
        
        # Latency metrics
        if self.transcription_latency_p99:
            latest = self.transcription_latency_p99[-1]
            lines.append(f"whisper_latency_ms_p99 {latest.value}")
        
        if self.transcription_latency_p99_9:
            latest = self.transcription_latency_p99_9[-1]
            lines.append(f"whisper_latency_ms_p99_9 {latest.value}")
        
        # Throughput
        if self.requests_per_second:
            latest = self.requests_per_second[-1]
            lines.append(f"whisper_requests_per_second {latest.value}")
        
        # Connections
        if self.concurrent_connections:
            latest = self.concurrent_connections[-1]
            lines.append(f"whisper_concurrent_connections {latest.value}")
        
        # Errors
        error_count = len(self.transcription_errors_total)
        lines.append(f"whisper_transcription_errors_total {error_count}")
        
        timeout_count = len(self.timeouts_total)
        lines.append(f"whisper_timeouts_total {timeout_count}")
        
        oom_count = len(self.gpu_oom_total)
        lines.append(f"whisper_gpu_oom_total {oom_count}")
        
        # GPU metrics
        if self.gpu_memory_usage_bytes:
            latest = self.gpu_memory_usage_bytes[-1]
            lines.append(f"whisper_gpu_memory_bytes {latest.value}")
        
        if self.gpu_utilization_percent:
            latest = self.gpu_utilization_percent[-1]
            lines.append(f"whisper_gpu_utilization_percent {latest.value}")
        
        if self.queue_depth_per_gpu:
            latest = self.queue_depth_per_gpu[-1]
            lines.append(f"whisper_gpu_queue_depth_avg {latest.value}")
        
        # Business metrics
        if self.audio_hours_processed_total:
            total = sum(m.value for m in self.audio_hours_processed_total)
            lines.append(f"whisper_audio_hours_processed_total {total}")
        
        return "\n".join(lines)


class AlertingRules:
    """Define when to alert based on metrics"""
    
    def __init__(self):
        self.alerts: List[Alert] = []
    
    def evaluate(self, metrics: PrometheusMetrics) -> List[Alert]:
        """Evaluate all alerting rules"""
        
        self.alerts = []
        
        # Rule 1: p99 latency too high
        if metrics.transcription_latency_p99:
            p99 = metrics.transcription_latency_p99[-1].value
            if p99 > 150:
                self.alerts.append(Alert(
                    severity=AlertSeverity.CRITICAL if p99 > 200 else AlertSeverity.WARNING,
                    metric="transcription_latency_p99",
                    current_value=p99,
                    threshold=150,
                    message=f"p99 latency high: {p99:.0f}ms (target: <100ms)",
                    action="Check GPU queue depth, reduce concurrent connections, or scale up",
                ))
        
        # Rule 2: GPU memory pressure
        if metrics.gpu_memory_usage_bytes:
            memory_gb = metrics.gpu_memory_usage_bytes[-1].value / 1e9
            if memory_gb > 20:  # 20GB on 24GB A30
                self.alerts.append(Alert(
                    severity=AlertSeverity.WARNING,
                    metric="gpu_memory_usage",
                    current_value=memory_gb,
                    threshold=20,
                    message=f"GPU memory pressure: {memory_gb:.1f}GB used (limit: 24GB)",
                    action="Reduce batch size, reduce concurrent connections, or monitor for OOM",
                ))
        
        # Rule 3: High error rate
        if len(metrics.transcription_errors_total) > 10:
            error_rate = len(metrics.transcription_errors_total) / max(1, len(metrics.successful_transcriptions_total) + len(metrics.transcription_errors_total))
            if error_rate > 0.01:  # >1% errors
                self.alerts.append(Alert(
                    severity=AlertSeverity.CRITICAL,
                    metric="error_rate",
                    current_value=error_rate * 100,
                    threshold=1.0,
                    message=f"High error rate: {error_rate*100:.1f}% (target: <0.1%)",
                    action="Check logs for OOM, GPU errors, or network issues",
                ))
        
        # Rule 4: Queue depth growing
        if metrics.queue_depth_per_gpu:
            queue_depth = metrics.queue_depth_per_gpu[-1].value
            if queue_depth > 20:
                self.alerts.append(Alert(
                    severity=AlertSeverity.WARNING,
                    metric="queue_depth",
                    current_value=queue_depth,
                    threshold=20,
                    message=f"GPU queue depth high: {queue_depth:.0f} (target: <5)",
                    action="System overloaded. Scale up or reduce traffic.",
                ))
        
        # Rule 5: Timeout spike
        if len(metrics.timeouts_total) > 5:
            self.alerts.append(Alert(
                severity=AlertSeverity.WARNING,
                metric="timeouts",
                current_value=len(metrics.timeouts_total),
                threshold=5,
                message=f"Request timeouts detected: {len(metrics.timeouts_total)} timeouts",
                action="Network issues or system overload. Check connectivity.",
            ))
        
        # Rule 6: GPU OOM
        if metrics.gpu_oom_total:
            self.alerts.append(Alert(
                severity=AlertSeverity.CRITICAL,
                metric="gpu_oom",
                current_value=len(metrics.gpu_oom_total),
                threshold=0,
                message=f"GPU out of memory: {len(metrics.gpu_oom_total)} OOM events",
                action="Reduce batch size immediately. Investigate what caused spike.",
            ))
        
        return self.alerts


class OperationalDashboard:
    """What to display on ops dashboard"""
    
    @staticmethod
    def print_dashboard(metrics: PrometheusMetrics, alerts: List[Alert]):
        """Print a simple ops dashboard"""
        
        print("\n" + "="*70)
        print("OPERATIONAL DASHBOARD: Whisper Streaming")
        print("="*70)
        print(f"Updated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # Status
        print("STATUS")
        print("─"*70)
        
        if not alerts:
            print("🟢 All systems operational")
        else:
            critical_count = sum(1 for a in alerts if a.severity == AlertSeverity.CRITICAL)
            warning_count = sum(1 for a in alerts if a.severity == AlertSeverity.WARNING)
            
            if critical_count > 0:
                print(f"🔴 CRITICAL: {critical_count} issue(s)")
            if warning_count > 0:
                print(f"🟡 WARNING: {warning_count} issue(s)")
        
        # Performance metrics
        print("\nPERFORMANCE")
        print("─"*70)
        
        if metrics.transcription_latency_p99:
            p99 = metrics.transcription_latency_p99[-1].value
            status = "✓" if p99 < 100 else "⚠" if p99 < 150 else "✗"
            print(f"{status} p99 latency:        {p99:7.1f}ms (target: <100ms)")
        
        if metrics.requests_per_second:
            rps = metrics.requests_per_second[-1].value
            print(f"  Throughput:          {rps:7.1f} req/s")
        
        if metrics.concurrent_connections:
            conc = int(metrics.concurrent_connections[-1].value)
            print(f"  Concurrent requests: {conc:7d}")
        
        # Resource usage
        print("\nRESOURCES")
        print("─"*70)
        
        if metrics.gpu_memory_usage_bytes:
            mem_gb = metrics.gpu_memory_usage_bytes[-1].value / 1e9
            status = "✓" if mem_gb < 18 else "⚠" if mem_gb < 22 else "✗"
            print(f"{status} GPU memory:         {mem_gb:7.1f}GB / 24GB ({mem_gb/24*100:5.1f}%)")
        
        if metrics.gpu_utilization_percent:
            util = metrics.gpu_utilization_percent[-1].value
            status = "✓" if 50 < util < 85 else "⚠"
            print(f"{status} GPU utilization:    {util:7.1f}%")
        
        if metrics.queue_depth_per_gpu:
            queue = int(metrics.queue_depth_per_gpu[-1].value)
            status = "✓" if queue < 5 else "⚠" if queue < 15 else "✗"
            print(f"{status} GPU queue depth:    {queue:7d}")
        
        # Errors
        print("\nRELIABILITY")
        print("─"*70)
        
        error_total = len(metrics.transcription_errors_total)
        timeout_total = len(metrics.timeouts_total)
        oom_total = len(metrics.gpu_oom_total)
        
        print(f"  Transcription errors: {error_total:7d}")
        print(f"  Timeouts:             {timeout_total:7d}")
        print(f"  GPU OOM events:       {oom_total:7d}")
        
        # Alerts
        if alerts:
            print("\nACTIVE ALERTS")
            print("─"*70)
            
            for alert in alerts:
                emoji = "🔴" if alert.severity == AlertSeverity.CRITICAL else "🟡"
                print(f"\n{emoji} [{alert.severity.value}] {alert.metric}")
                print(f"   {alert.message}")
                print(f"   Action: {alert.action}")
        
        print("\n" + "="*70)
    
    @staticmethod
    def print_runbook():
        """Print operational runbook for common issues"""
        
        print("\n" + "="*70)
        print("OPERATIONAL RUNBOOK: Common Issues & Fixes")
        print("="*70)
        
        runbook = """
ISSUE: p99 latency > 150ms
├─ Symptom: Users report laggy voice responses
├─ Check:
│  1. GPU utilization > 90%? → System overloaded
│  2. Queue depth > 10? → Too many concurrent requests
│  3. GPU memory > 22GB? → Approaching limit
├─ Fix:
│  1. Scale up to additional GPU instance
│  2. Reduce max concurrent connections
│  3. Alert marketing to reduce traffic until scaled
└─ Timeline: 5-10 minutes to scale up

ISSUE: GPU out of memory
├─ Symptom: Transcription errors, system crashes
├─ Check:
│  1. Sudden spike in concurrent users?
│  2. Batch size changed recently?
│  3. Memory leak in code?
├─ Fix:
│  1. Reduce batch size from 3 to 2
│  2. Reduce concurrent connection limit to 8
│  3. Restart service to clear memory
│  4. Investigate code changes if persistent
└─ Timeline: 2-5 minutes to restore service

ISSUE: High error rate (>1%)
├─ Symptom: Some requests failing silently
├─ Check:
│  1. GPU timeouts? Check logs for CUDA errors
│  2. Network issues? Check connectivity
│  3. Service issues? Check health endpoint
├─ Fix:
│  1. Restart failing pods
│  2. Check if backend service is up
│  3. Roll back recent changes
└─ Timeline: 5-15 minutes to investigate + fix

ISSUE: Queue depth growing (> 15)
├─ Symptom: Requests queued for seconds
├─ Check:
│  1. GPU utilization at 100%?
│  2. Concurrent requests growing?
│  3. Inference time degrading?
├─ Fix:
│  1. Start scaling (takes 2-3 minutes)
│  2. Temporarily reduce batch size
│  3. Alert users to retry
└─ Timeline: 2-3 minutes to scale, then resolve

MONITORING CADENCE
──────────────────
Every 30 seconds:  Record p99 latency, throughput, concurrent connections
Every 5 minutes:   Check for alerts, review queue depth
Every hour:        Analyze trends, check for anomalies
Every day:         Review error budget, capacity headroom
Every week:        Capacity planning, cost analysis
"""
        
        print(runbook)


def example_usage():
    """Show how to use these in production"""
    
    print("\n" + "="*70)
    print("EXAMPLE: Using These Metrics in Production")
    print("="*70)
    
    # Create metrics collector
    metrics = PrometheusMetrics()
    
    # Simulate some measurements over time
    print("\nSimulating 5 minutes of metrics collection...\n")
    
    scenarios = [
        # Normal operation
        (92.5, 101.2, 118.3, 11.5, 3, "Normal load"),
        (91.8, 100.9, 115.2, 11.8, 3, "Normal load"),
        (93.2, 102.1, 120.1, 11.2, 3, "Normal load"),
        
        # Load spike
        (95.1, 125.3, 145.2, 9.8, 8, "Load spike"),
        (98.2, 135.5, 160.1, 8.5, 10, "Load spike"),
        
        # Recovery
        (94.3, 115.2, 130.5, 10.2, 7, "Recovering"),
        (92.1, 103.4, 119.2, 11.1, 4, "Back to normal"),
    ]
    
    for p50, p99, p99_9, rps, conc, label in scenarios:
        metrics.record_latency(p50, p99, p99_9)
        metrics.record_throughput(rps, conc)
        metrics.record_gpu_metrics(6.5 + conc*0.1, 50 + rps*3, conc, time.time())
    
    # Evaluate alerts
    alerter = AlertingRules()
    alerts = alerter.evaluate(metrics)
    
    # Print dashboard
    OperationalDashboard.print_dashboard(metrics, alerts)
    
    # Print Prometheus format
    print("\nPROMETHEUS FORMAT (for Grafana):")
    print("─"*70)
    print(metrics.get_prometheus_format())
    
    # Print runbook
    OperationalDashboard.print_runbook()


if __name__ == "__main__":
    example_usage()
