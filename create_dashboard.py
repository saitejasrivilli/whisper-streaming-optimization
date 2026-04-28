import json
import matplotlib.pyplot as plt
import numpy as np

# Load metrics
with open('production_metrics.json') as f:
    data = json.load(f)

# Extract data
times = range(len(data))
p99s = [m['p99'] for m in data]
errors = [m['error_rate'] for m in data]
qps = [m['qps'] for m in data]
gpu = [m['gpu'] for m in data]

# Create figure
fig, axes = plt.subplots(2, 2, figsize=(12, 8))

# Plot 1: p99 Latency
axes[0, 0].plot(times, p99s, 'b-', linewidth=2, label='p99 latency')
axes[0, 0].axhline(y=300, color='r', linestyle='--', label='Alert threshold')
axes[0, 0].set_ylabel('Latency (ms)', fontsize=10)
axes[0, 0].set_title('p99 Latency Over Time')
axes[0, 0].legend()
axes[0, 0].grid(True, alpha=0.3)

# Plot 2: Error Rate
axes[0, 1].plot(times, errors, 'r-', linewidth=2, label='Error rate')
axes[0, 1].axhline(y=1.0, color='orange', linestyle='--', label='Alert threshold')
axes[0, 1].set_ylabel('Error Rate (%)', fontsize=10)
axes[0, 1].set_title('Error Rate Over Time')
axes[0, 1].legend()
axes[0, 1].grid(True, alpha=0.3)

# Plot 3: QPS
axes[1, 0].plot(times, qps, 'g-', linewidth=2, label='QPS')
axes[1, 0].set_ylabel('Requests/sec', fontsize=10)
axes[1, 0].set_title('Throughput Over Time')
axes[1, 0].legend()
axes[1, 0].grid(True, alpha=0.3)

# Plot 4: GPU Utilization
axes[1, 1].plot(times, gpu, 'm-', linewidth=2, label='GPU util')
axes[1, 1].axhline(y=90, color='r', linestyle='--', label='Alert threshold')
axes[1, 1].set_ylabel('GPU Utilization (%)', fontsize=10)
axes[1, 1].set_title('GPU Utilization Over Time')
axes[1, 1].set_xlabel('Time Window', fontsize=10)
axes[1, 1].legend()
axes[1, 1].grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('production_dashboard.png', dpi=150)
print("✓ Dashboard saved to production_dashboard.png")
print(f"  - {len(data)} data points")
print(f"  - p99 range: {min(p99s):.0f}ms - {max(p99s):.0f}ms")
print(f"  - Error rate: {min(errors):.2f}% - {max(errors):.2f}%")
print(f"  - QPS range: {min(qps):.1f} - {max(qps):.1f}")
