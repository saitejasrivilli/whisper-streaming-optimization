import asyncio, logging, time
from dataclasses import dataclass
import numpy as np, torch, whisper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class StreamingMetrics:
    first_token_latencies: list
    chunk_process_latencies: list
    end_to_end_latencies: list
    gpu_utilization: float
    memory_used_mb: float
    throughput_req_per_sec: float
    
    def summarize(self):
        return {
            "p99_ms": np.percentile(self.chunk_process_latencies, 99) if self.chunk_process_latencies else 0,
        }

class StreamingWhisper:
    def __init__(self):
        logger.info("Loading Whisper...")
        self.model = whisper.load_model("base")
        self.device = torch.device("cpu")
        self.model = self.model.to(self.device)
        self.metrics = StreamingMetrics([], [], [], 0.0, 0.0, 0.0)
    
    def process(self, audio: np.ndarray):
        return self.model.transcribe(audio, language="en", verbose=False)
    
    def get_metrics(self):
        return self.metrics.summarize()

async def client_stream(cid, dur=3.0):
    sr, chunk_sz = 16000, 1600
    total = int(sr * dur)
    audio = np.random.randn(total).astype(np.float32) * 0.05
    sent = 0
    while sent < total:
        await asyncio.sleep(0.1)
        end = min(sent + chunk_sz, total)
        yield audio[sent:end]
        sent = end

async def benchmark(num_clients=2):
    logger.info(f"Starting: {num_clients} clients")
    engine = StreamingWhisper()
    start = time.time()
    
    async def run_client(cid):
        count = 0
        async for chunk in client_stream(cid, 3.0):
            t0 = time.time()
            result = await asyncio.to_thread(engine.process, chunk)
            lat = (time.time() - t0) * 1000
            count += 1
            engine.metrics.chunk_process_latencies.append(lat)
            logger.info(f"  client_{cid}: {lat:.1f}ms")
    
    await asyncio.gather(*[run_client(i) for i in range(num_clients)])
    elapsed = time.time() - start
    
    logger.info("="*50)
    logger.info("RESULTS")
    logger.info("="*50)
    m = engine.get_metrics()
    logger.info(f"p99 latency: {m['p99_ms']:.1f}ms")
    logger.info(f"Total time: {elapsed:.1f}s")
    logger.info("="*50)

if __name__ == "__main__":
    asyncio.run(benchmark(num_clients=2))
