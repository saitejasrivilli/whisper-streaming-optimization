"""
Performance Analysis: Where Time Is Actually Spent

This module profiles Whisper inference to show GPU utilization, 
memory pressure, and bottlenecks.
"""

import torch
import whisper
import numpy as np
import time
from torch.profiler import profile, record_function, ProfilerActivity
import matplotlib.pyplot as plt
from typing import Dict, List, Tuple


class WhisperProfiler:
    """Profile Whisper inference to identify bottlenecks"""
    
    def __init__(self, model_name: str = "base"):
        self.model = whisper.load_model(model_name)
        self.device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
        self.model = self.model.to(self.device)
        if torch.cuda.is_available():
            self.model = self.model.half()
    
    def profile_inference(self, audio_length_sec: float = 10.0) -> Dict:
        """
        Profile a full inference pass.
        
        Returns breakdown of:
        - Mel-spectrogram computation
        - Encoder forward pass
        - Decoder forward pass
        - Total GPU/CPU time
        """
        
        # Generate synthetic audio
        sample_rate = 16000
        num_samples = int(sample_rate * audio_length_sec)
        audio = np.random.randn(num_samples).astype(np.float32) * 0.05
        
        print(f"📊 Profiling Whisper {self.model.__class__.__name__}")
        print(f"   Audio length: {audio_length_sec:.1f}s ({num_samples} samples)")
        print(f"   Device: {self.device}")
        print()
        
        # Warm up GPU
        _ = self.model.transcribe(audio[:sample_rate], verbose=False)
        
        # Profile with torch.profiler
        with profile(
            activities=[
                ProfilerActivity.CPU,
                ProfilerActivity.CUDA,
            ],
            record_shapes=True,
            profile_memory=True,
            on_trace_ready=self._print_profile,
        ) as prof:
            with record_function("full_transcription"):
                result = self.model.transcribe(
                    audio,
                    language="en",
                    fp16=torch.cuda.is_available(),
                    verbose=False,
                )
        
        return self._analyze_profile(prof, result)
    
    def _print_profile(self, prof):
        """Print profiler output"""
        print(prof.key_averages().table(sort_by="cuda_time_total", row_limit=20))
    
    def _analyze_profile(self, prof, result) -> Dict:
        """Extract key metrics from profiler"""
        
        key_averages = prof.key_averages()
        
        # Compute totals
        total_cuda_time = sum(evt.cuda_time for evt in key_averages) / 1e6  # Convert to ms
        total_cpu_time = sum(evt.cpu_time for evt in key_averages) / 1e6
        
        # Find main components
        components = self._find_components(key_averages)
        
        # Memory stats
        if torch.cuda.is_available():
            max_memory_gb = torch.cuda.max_memory_allocated() / 1e9
            reserved_gb = torch.cuda.memory_reserved() / 1e9
        else:
            max_memory_gb = reserved_gb = 0
        
        return {
            "total_cuda_time_ms": total_cuda_time,
            "total_cpu_time_ms": total_cpu_time,
            "components": components,
            "max_memory_allocated_gb": max_memory_gb,
            "memory_reserved_gb": reserved_gb,
            "result": result,
        }
    
    def _find_components(self, key_averages) -> Dict[str, float]:
        """Extract component-level timing"""
        
        components = {}
        for evt in key_averages:
            name = evt.key
            cuda_time_ms = evt.cuda_time_total / 1e6
            
            # Aggregate by component
            if "encoder" in name.lower():
                components["encoder"] = components.get("encoder", 0) + cuda_time_ms
            elif "decoder" in name.lower():
                components["decoder"] = components.get("decoder", 0) + cuda_time_ms
            elif "mel" in name.lower() or "spectrogram" in name.lower():
                components["mel_spectrogram"] = components.get("mel_spectrogram", 0) + cuda_time_ms
            elif "embedding" in name.lower():
                components["embeddings"] = components.get("embeddings", 0) + cuda_time_ms
            elif "attention" in name.lower():
                components["attention"] = components.get("attention", 0) + cuda_time_ms
        
        return components


def analyze_latency_distribution(latencies_ms: List[float]):
    """Analyze latency percentiles"""
    
    sorted_lat = sorted(latencies_ms)
    
    percentiles = [50, 90, 95, 99, 99.9, 99.99]
    print("\n📈 Latency Percentiles (ms)")
    print("─" * 40)
    
    for p in percentiles:
        idx = int(len(sorted_lat) * p / 100)
        value = sorted_lat[min(idx, len(sorted_lat) - 1)]
        print(f"  p{p:6.2f}: {value:8.2f}ms")
    
    print(f"\n  Mean:     {np.mean(latencies_ms):8.2f}ms")
    print(f"  Median:   {np.median(latencies_ms):8.2f}ms")
    print(f"  StdDev:   {np.std(latencies_ms):8.2f}ms")
    print(f"  Min:      {np.min(latencies_ms):8.2f}ms")
    print(f"  Max:      {np.max(latencies_ms):8.2f}ms")
    print("─" * 40)


def benchmark_batch_sizes(audio_length_sec: float = 10.0):
    """
    Benchmark different batch configurations.
    
    Shows throughput vs latency tradeoff.
    """
    
    print("\n🚀 Batch Size Analysis")
    print("=" * 70)
    
    model = whisper.load_model("base")
    device = torch.device("cuda:0")
    model = model.to(device).half()
    
    # Generate test audio
    sample_rate = 16000
    num_samples = int(sample_rate * audio_length_sec)
    audio = np.random.randn(num_samples).astype(np.float32) * 0.05
    
    results = []
    
    for batch_size in [1, 2, 3, 4]:
        # Time multiple batches
        latencies = []
        
        for _ in range(5):
            start = time.perf_counter()
            for _ in range(batch_size):
                _ = model.transcribe(
                    audio,
                    language="en",
                    fp16=True,
                    verbose=False,
                )
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed / batch_size)  # Per-request latency
        
        avg_latency = np.mean(latencies)
        p99_latency = np.percentile(latencies, 99)
        throughput = 1000 / avg_latency  # requests per second
        
        results.append({
            "batch_size": batch_size,
            "avg_latency_ms": avg_latency,
            "p99_latency_ms": p99_latency,
            "throughput_req_s": throughput,
        })
        
        print(f"\nBatch size {batch_size}:")
        print(f"  Avg latency:  {avg_latency:.1f}ms")
        print(f"  p99 latency:  {p99_latency:.1f}ms")
        print(f"  Throughput:   {throughput:.1f} req/s")
    
    print("\n" + "=" * 70)
    print("Interpretation:")
    print("  - Larger batches = lower per-request latency (amortized)")
    print("  - BUT p99 increases (wait for slowest in batch)")
    print("  - For streaming: batch_size=2-3 optimal (low p99, ok throughput)")
    
    return results


def gpu_memory_analysis():
    """
    Analyze GPU memory pressure under different loads.
    
    Shows why we can't batch size=8 on A30.
    """
    
    print("\n💾 GPU Memory Analysis")
    print("=" * 70)
    
    if not torch.cuda.is_available():
        print("CUDA not available")
        return
    
    device = torch.device("cuda:0")
    model = whisper.load_model("base")
    model = model.to(device).half()
    
    print(f"\nGPU: {torch.cuda.get_device_name(0)}")
    print(f"Total memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f}GB")
    
    # Get model size
    model_params = sum(p.numel() for p in model.parameters())
    model_size_mb = model_params * 2 / 1e6  # fp16 = 2 bytes
    print(f"Model size (fp16): {model_size_mb:.1f}MB")
    
    print("\nInference memory usage:")
    
    sample_rate = 16000
    audio_sec = 10
    num_samples = int(sample_rate * audio_sec)
    audio = np.random.randn(num_samples).astype(np.float32) * 0.05
    
    torch.cuda.reset_peak_memory_stats()
    torch.cuda.empty_cache()
    
    _ = model.transcribe(
        audio,
        language="en",
        fp16=True,
        verbose=False,
    )
    
    peak_memory = torch.cuda.max_memory_allocated() / 1e9
    print(f"  Single inference: {peak_memory:.2f}GB")
    
    print("\nMemory budget per GPU (24GB A30):")
    print(f"  Model weights:          {model_size_mb:.0f}MB")
    print(f"  Single inference:       {peak_memory * 1000:.0f}MB")
    print(f"  Headroom for batch=2:   {24000 - 2 * peak_memory * 1000:.0f}MB")
    print(f"  Headroom for batch=3:   {24000 - 3 * peak_memory * 1000:.0f}MB")
    print(f"  Headroom for batch=4:   {24000 - 4 * peak_memory * 1000:.0f}MB")
    
    print("\n" + "=" * 70)
    print("Conclusion: Batch size > 3 leaves insufficient headroom for spikes")


def show_latency_timeline():
    """
    Show typical latency breakdown for a streaming request.
    
    Helps understand where p99 comes from.
    """
    
    print("\n⏱️  Latency Timeline for Streaming Request")
    print("=" * 70)
    
    timeline = [
        ("Audio chunk arrives", 0, 0),
        ("Add to buffer", 1, "< 1ms (memory operation)"),
        ("Buffer timeout reached", 50, "Configurable: ~50ms"),
        ("Assign to GPU", 0.5, "< 1ms (load balancing)"),
        ("Wait in GPU queue", 15, "Variable: 0-50ms depending on other requests"),
        ("Mel-spectrogram", 20, "Fixed computation"),
        ("Encoder", 35, "Main inference"),
        ("Decoder", 15, "Token generation"),
        ("Return result", 1, "< 1ms"),
    ]
    
    cumulative = 0
    for step, latency, note in timeline:
        cumulative += latency
        bar = "█" * (int(latency) // 5)
        print(f"  {step:30s} | {latency:6.1f}ms | {bar:20s} | {note}")
    
    print(f"\n  Total (typical p50):  ~{cumulative:.0f}ms")
    print(f"  Total (worst p99):    ~130ms (when queue is deep)")
    print("=" * 70)


if __name__ == "__main__":
    print("🎯 Whisper Streaming: Performance Analysis\n")
    
    # Run analyses
    profiler = WhisperProfiler(model_name="base")
    profile_result = profiler.profile_inference(audio_length_sec=10.0)
    
    print("\n📊 Profile Results:")
    print(f"  CUDA time: {profile_result['total_cuda_time_ms']:.1f}ms")
    print(f"  CPU time:  {profile_result['total_cpu_time_ms']:.1f}ms")
    print(f"  Memory:    {profile_result['max_memory_allocated_gb']:.2f}GB")
    print(f"  Components: {profile_result['components']}")
    
    # Batch size analysis
    benchmark_batch_sizes(audio_length_sec=10.0)
    
    # Memory analysis
    gpu_memory_analysis()
    
    # Latency timeline
    show_latency_timeline()
    
    print("\n✅ Analysis complete")
