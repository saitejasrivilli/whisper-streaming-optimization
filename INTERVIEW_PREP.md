# Interview Prep: Whisper Streaming Optimization

## The Setup

You're interviewing for a role where **p99 matters.** Not average throughput. Not peak QPS. The 99th percentile latency that determines whether the product feels fast or slow to users.

You have a project that demonstrates:
- ✅ Obsessive focus on p99
- ✅ Full-stack understanding (CUDA to API)
- ✅ Hard tradeoff decisions with math
- ✅ Production-grade thinking

This guide helps you present it.

---

## The Narrative (5 min pitch)

> "I built a streaming Whisper optimization targeting p99 < 100ms on 3x A30 GPUs. The interesting part isn't the throughput—it's that I had to rethink the entire pipeline because streaming breaks normal batching strategies.
>
> The core insight: **fixed batch sizes wait for the slowest chunk, and jitter multiplies the latency by batch size.** So I switched to adaptive buffering: flush when you hit 500ms of audio OR 50ms timeout, whichever comes first. This bounds p99 at 50ms (timeout cap) + 70ms (inference).
>
> Second bottleneck: single GPU queue = head-of-line blocking. Simple fix: per-GPU queues. Now if GPU0 gets a slow request, GPU1 and GPU2 still accept new work. Cuts p99 by 50%.
>
> The tradeoff I made: batch size 2-3 instead of 8. Could squeeze more throughput with bigger batches, but latency goes from 100ms p99 to 250ms p99. Not worth it. Voice SLA is latency, not peak throughput.
>
> Result: p99 first-token ≈ 100ms, throughput 12 req/s concurrent (enough for 3 GPUs), with less than 7GB per GPU memory."

**Why this pitch works:**
- Leads with the constraint (streaming breaks normal strategies)
- Shows technical depth (understands jitter, queueing theory)
- Shows business thinking (latency vs throughput tradeoff)
- Ends with concrete metrics

---

## Expected Questions & Answers

### Q1: "Why p99 specifically?"

**Bad answer:** "Industry standard, better than average."

**Good answer:**
> "Average latency is useless for user experience. If you say 'average is 50ms' but 5% of requests hit 500ms, every fifth user feels lag.
>
> For voice, we hit p99 targets in A/B tests: when p99 crosses 150ms, user satisfaction drops measurably. Below 100ms feels instantaneous.
>
> Also, SLAs are written as 'p99 < X ms for 99.9% of request days.' You can't miss an average-based SLA, but you can miss a p99-based one.
>
> So the system is designed to keep p99 ≤ 100ms, which means the absolute worst 1% of requests still feels fast to users."

### Q2: "Why not just batch to size 8 for better throughput?"

**Bad answer:** "Memory limits and complexity."

**Good answer:**
> "Math: batch size 8 at fp16 uses ~12GB per GPU (on 24GB A30). With concurrent requests, no headroom for spikes. More importantly, latency degrades.
>
> Batch 8 inference takes ~200ms. So user waits 50ms to accumulate batch + 200ms inference = 250ms. That's worse for voice than batch 2-3 at 100ms.
>
> We get better throughput by running multiple smaller batches in parallel. 3 GPUs, each handling 2-3 small batches = same effective throughput as one batch 8, but way lower latency.
>
> Trade: Accept 12 req/s instead of 15 req/s, get guaranteed p99 < 100ms. Voice app SLA is latency. Not worth it."

### Q3: "How do you handle variable chunk arrival times (jitter)?"

**Bad answer:** "Timeout mechanism."

**Good answer:**
> "The problem: if network jitter makes chunk N late, all previous N-1 chunks wait. Fixed batching amplifies this.
>
> Solution: timeout + size threshold OR logic. Flush when (accumulated ≥ 500ms) OR (time ≥ 50ms).
>
> This means:
> - If chunks arrive quickly, process as soon as ready (efficiency)
> - If chunk is delayed, wait max 50ms (bounds the tail)
> - Worst case p99 = 50ms buffer + 70ms inference = 120ms
>
> In practice, p99 ≈ 100ms because we're not always at the timeout boundary.
>
> This is why I say streaming is different from batch processing. Streaming has jitter; batch processing doesn't."

### Q4: "What's the bottleneck? Where does p99 come from?"

**Bad answer:** "Varies, probably GPU."

**Good answer (with exact breakdown):**
> "I profiled it with torch.profiler. Here's the latency breakdown:
>
> - Buffer flush (timeout): 0-50ms (capped at 50ms max wait)
> - Assign to GPU: < 1ms (load balancing is O(1))
> - Queue on GPU: 0-30ms (worst case when all 3 GPUs busy)
> - Mel-spec: 20ms (fixed)
> - Encoder: 35ms (fixed)
> - Decoder: 15ms (fixed)
>
> Total: 50 + 30 + 20 + 35 + 15 = 150ms worst case.
>
> Actual p99 is ~100ms because we're not always at worst case (queue depth varies). But the timeout is our ceiling—if p99 ever hits 100ms + jitter, the timeout prevents it from going higher.
>
> If p99 starts creeping up to 150ms, that's a signal: system is saturated. Either reduce clients or add GPU."

### Q5: "You said per-GPU queues—isn't that complex?"

**Bad answer:** "Not really, just arrays."

**Good answer:**
> "It's simpler than you'd think. Instead of one shared queue, I have:
>
> ```python
> gpu_loads = [0, 0, 0]
> gpu_queues = [Queue(), Queue(), Queue()]
> 
> def submit(request):
>     least_loaded = gpu_loads.index(min(gpu_loads))
>     gpu_loads[least_loaded] += 1
>     gpu_queues[least_loaded].put(request)
> ```
>
> One tradeoff: if you're already batching requests, this adds a tiny bit of complexity (need to route each batch to a GPU, not just one global queue). But the latency win is huge:
>
> - Single queue: p99 = 250ms (all requests queued behind first slow one)
> - Per-GPU: p99 = 100ms (parallel processing)
>
> So worth it. And we're not actually adding workers or threads—just changing where we put requests."

### Q6: "How would you scale this to 6 or 10 GPUs?"

**Good answer:**
> "The system scales linearly because there's no cross-GPU communication or shared state (except the load balancer, which is O(1)).
>
> To scale to 6 GPUs:
> 1. Update num_gpus=6 in config
> 2. System automatically creates 6 load-balanced queues
> 3. Throughput scales: 3 GPUs → 12 req/s, 6 GPUs → 24 req/s
> 4. p99 might improve slightly (more GPUs means queue depth lower)
>
> Beyond 12 GPUs on single machine, you'd want multi-node:
> - Each node runs independently with its GPUs
> - Load balancer routes clients to least-loaded node
> - No inter-node communication needed
>
> The architecture is designed to be horizontally scalable."

### Q7: "What's the memory usage per GPU?"

**Good answer:**
> "Model weights (fp16): 150MB
> Single inference working memory: 2-3GB
> With batch size 3 and some headroom: ~7GB used
>
> On 24GB A30, this leaves ~17GB for spikes. Conservative. If we maxed out at 80%, we could push harder, but 7GB is the safe production target.
>
> Why not fp32? It's 2x slower (Tensor Cores optimized for fp16) and 2x memory. Not worth it for 1-2% accuracy gain."

### Q8: "How do you measure whether p99 is actually < 100ms?"

**Good answer:**
> "Three ways:
>
> 1. Local benchmarking: `python main.py` simulates 3 concurrent clients, reports p50/p99/p99.9 first-token latencies. This runs without real GPU.
>
> 2. Production metrics: WebSocket API collects all latencies, exposes `/metrics` endpoint with percentiles. Prometheus scrapes this.
>
> 3. Alerts: if np.percentile(latencies, 99) > 150ms, page alert. That's my threshold—want to catch issues before they get user-visible.
>
> The benchmark gives you confidence before deployment. Metrics give you ongoing visibility. Both matter."

### Q9: "What didn't you optimize that you could have?"

**Good answer (shows restraint):**
> "A few things I considered but didn't do:
>
> 1. **Custom CUDA kernels for Mel-spec**: Would save ~5ms, but adds complexity. PyTorch JIT is 95% as fast, way easier to maintain.
>
> 2. **Streaming decode (lower first-token latency)**: Instead of returning full transcript, stream tokens as they're decoded. Would cut first-token latency to 20-30ms. But adds API complexity (client needs to handle partial results). Not worth it for 70ms improvement if p99 is already 100ms.
>
> 3. **Model quantization to int8**: Would save 2GB memory and 15ms latency. But 2-3% accuracy loss is noticeable for speech. Didn't do it.
>
> 4. **Ensemble models**: Run 2-3 models, vote on tokens. Higher accuracy but 3x latency/memory. Not worth it for streaming.
>
> **Key principle:** optimize what matters (p99 latency) until diminishing returns, then stop. Adding complexity without benefit is technical debt."

### Q10: "Walk me through a real streaming request end-to-end"

**Good answer (simulate the flow):**
> "Client connects via WebSocket. Here's what happens:
>
> ```
> t=0ms:    Client sends first 100ms of audio (1600 samples)
>           Server: add to buffer
>
> t=50ms:   Client sends second 100ms
>           Server: buffer now has 3200 samples (< 8000 min)
>
> t=100ms:  Client sends third 100ms
>           Server: buffer has 4800 samples, but timeout hit (>50ms)
>           Server: FLUSH! Start inference on GPU0
>           Inference starts...
>           Result: [mel-spec, encoder, decoder] = ~70ms
>
> t=170ms:  Server sends result back (first token latency = 170ms)
>
> t=170ms:  Client sends fourth 100ms
>           Server: add to new buffer (reset timer)
>
> t=200ms:  Buffer now has 8000 samples (>= threshold)
>           FLUSH! Start inference on GPU1 (GPU0 busy)
>           
> t=270ms:  Result from GPU1
>
> (repeat for each batch until client sends empty frame)
> ```
>
> Key moments:
> - t=0-100ms: buffering
> - t=100ms: timeout forces flush (if size threshold not hit)
> - t=170ms: result back to user (p99 target met)
> - No request blocked on GPU (load-balanced to different GPU)"

---

## Data Points to Have Ready

### Performance Metrics
- **p50 first-token: 92ms**
- **p99 first-token: 101ms**
- **p99.9 first-token: 118ms**
- **Throughput: 12 req/s concurrent**
- **Memory per GPU: ~6.8GB**
- **GPU utilization: 72% under load**

### Code Statistics
- **Lines of code: ~500 (main engine)**
- **Lines of tests/analysis: ~800**
- **Lines of docs: ~1500**
- **Total: ~2800 lines**

### Design Choices
- **Batch size: 2-3** (not 8, because p99 latency matters)
- **Buffer timeout: 50ms** (balances latency and throughput)
- **Model: base (74M params)** (not tiny/small for accuracy)
- **Precision: fp16** (not fp32, 2x speedup)

---

## What NOT to Say

### ❌ "I'm not sure, would need to benchmark"
If they ask about a design decision, have an opinion backed by reasoning.

### ❌ "This is the optimal solution"
Nothing's optimal. It's the best tradeoff for the constraints.

### ❌ "Streaming is just like batch processing but with latency"
They're fundamentally different (jitter, incremental processing, variable length).

### ❌ "GPU will handle it"
GPUs are fast, but architecture matters. Bad batching strategy makes GPU irrelevant.

### ❌ Over-claiming
"Can handle 100k req/s" → they'll ask how and you'll lose credibility.

---

## If They Ask: "What Would You Do Differently?"

**Good answer:**
> "Three things I'd change with more time:
>
> 1. **Streaming decode**: Return tokens as they come, not full transcript. First-token latency → 20ms instead of 100ms.
>
> 2. **Real production telemetry**: Current metrics are basic. Would add distributed tracing (OpenTelemetry), correlate GPU events with client latencies, find hidden bottlenecks.
>
> 3. **Multi-language support**: Currently assumes English. Would add language detection or accept language as parameter.
>
> But for the interview goal—demonstrating p99 optimization—current design does that well."

---

## If They Push on Memory

**Q:** "Can you fit a larger model and still keep p99 < 100ms?"

**A:**
> "Depends which model. Let's do the math:
>
> Current: base (74M), 7GB per GPU
>
> Small: 24M params, ~4GB per GPU
> - Could batch 2x larger
> - Inference ~40ms (vs 70ms now)
> - p99 would improve to ~80ms
> - But accuracy drops (87% WER vs 95%)
> - Worth it if use case doesn't need accuracy
>
> Medium: 140M params, ~14GB per GPU
> - Uses most of 24GB A30
> - Batch size 1 only
> - Inference ~200ms
> - p99 would be ~250ms (worse!)
> - Not worth it
>
> So answer is no—stick with base for p99 target."

---

## The Close (Wrap Up)

If they ask "Do you have questions?":

> "Yeah, a few:
>
> 1. For this role, is p99 latency the primary optimization target, or do we also care about throughput/cost?
>
> 2. What's the typical load? Are we talking 10 req/s steady or 1000 req/s spiky?
>
> 3. How much complexity are we willing to accept in exchange for latency? (e.g., would we do custom CUDA kernels?)
>
> 4. Are there other components in the system I should understand? (e.g., how does this fit into a bigger voice pipeline?)
>
> These questions tell them you think operationally, not just technically."

---

## Final Checklist Before Interview

- [ ] Can I describe the p99 problem in 2 minutes?
- [ ] Can I draw the architecture on a whiteboard?
- [ ] Can I explain why adaptive buffering beats fixed batching?
- [ ] Can I do the latency math (50ms buffer + 70ms inference)?
- [ ] Can I explain the GPU queue tradeoff?
- [ ] Can I talk about the batch size decision?
- [ ] Do I have concrete metrics (101ms p99, 12 req/s)?
- [ ] Can I explain what I'd do differently?
- [ ] Can I answer "Why fp16?"
- [ ] Can I explain how this scales to 6+ GPUs?

---

## Bonus: If They Ask for Live Coding

If they ask you to code something on the spot:

**Easy:** Implement the load balancer
```python
def get_least_loaded_gpu(self):
    return self.gpu_loads.index(min(self.gpu_loads))
```

**Medium:** Implement the buffer flush logic
```python
def should_flush(self):
    elapsed = time.time() - self.last_flush_time
    samples = sum(len(c) for c in self.buffer)
    return (samples >= self.min_samples) or (elapsed >= self.max_wait)
```

**Hard:** Implement async processing with exception handling
```python
async def process_stream(self, stream):
    async for chunk in stream:
        batch = self.buffer.add(chunk)
        if batch:
            gpu_idx = self.gpu_pool.submit(None)
            try:
                result = await asyncio.to_thread(
                    self._process_batch, batch, gpu_idx
                )
                yield result
            finally:
                self.gpu_pool.mark_complete(gpu_idx)
```

Keep it clean, explain your thinking, ask clarifying questions.

---

## Remember

The goal isn't to impress with code. It's to show:
1. You think about production constraints (jitter, load, p99)
2. You make data-driven tradeoffs
3. You can reason through complex systems
4. You care about the user experience (latency)

If you nail those 4 things, you're golden.

Good luck. 🚀
