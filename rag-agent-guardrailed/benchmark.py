#!/usr/bin/env python3
"""
Benchmark script for Vijil Docs Agent
Tests response times, rate limits, and cache effectiveness
"""
import asyncio
import aiohttp
import time
import statistics
from dataclasses import dataclass
from typing import List, Dict
import json

# Configuration
BASE_URL = "http://localhost:8000/v1/chat/completions"
MODEL = "vijil-docs-agent"

# Test queries (mix of similar and different queries to test caching)
TEST_QUERIES = [
    "What is Vijil?",
    "What is Vijil?",  # Duplicate to test cache
    "How do I use Vijil for evaluation?",
    "What are Vijil's main features?",
    "What is Vijil?",  # Another duplicate
    "Explain Vijil detectors",
    "How does Vijil evaluate LLMs?",
    "What trust dimensions does Vijil support?",
    "What is Vijil?",  # Test cache again
    "How do I get started with Vijil?",
]

@dataclass
class RequestResult:
    query: str
    response_time: float
    success: bool
    error: str = None
    cached: bool = False
    response_length: int = 0

async def make_request(session: aiohttp.ClientSession, query: str) -> RequestResult:
    """Make a single chat completion request."""
    start_time = time.time()
    
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": query}],
        "stream": False
    }
    
    try:
        async with session.post(BASE_URL, json=payload, timeout=aiohttp.ClientTimeout(total=60)) as response:
            elapsed = time.time() - start_time
            
            if response.status == 200:
                data = await response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                
                return RequestResult(
                    query=query,
                    response_time=elapsed,
                    success=True,
                    response_length=len(content)
                )
            else:
                error_text = await response.text()
                return RequestResult(
                    query=query,
                    response_time=elapsed,
                    success=False,
                    error=f"HTTP {response.status}: {error_text[:100]}"
                )
    except Exception as e:
        elapsed = time.time() - start_time
        return RequestResult(
            query=query,
            response_time=elapsed,
            success=False,
            error=str(e)
        )

async def run_sequential_test(queries: List[str]) -> List[RequestResult]:
    """Run requests sequentially (one at a time)."""
    print("\n" + "="*60)
    print("SEQUENTIAL TEST (1 request at a time)")
    print("="*60)
    
    results = []
    async with aiohttp.ClientSession() as session:
        for i, query in enumerate(queries, 1):
            print(f"\n[{i}/{len(queries)}] Testing: {query[:50]}...")
            result = await make_request(session, query)
            
            if result.success:
                print(f"  ✓ Success: {result.response_time:.2f}s ({result.response_length} chars)")
            else:
                print(f"  ✗ Failed: {result.error}")
            
            results.append(result)
            
            # Small delay between requests
            await asyncio.sleep(0.5)
    
    return results

async def run_concurrent_test(queries: List[str], concurrency: int) -> List[RequestResult]:
    """Run requests with specified concurrency level."""
    print(f"\n" + "="*60)
    print(f"CONCURRENT TEST ({concurrency} requests at a time)")
    print("="*60)
    
    results = []
    async with aiohttp.ClientSession() as session:
        # Process in batches
        for i in range(0, len(queries), concurrency):
            batch = queries[i:i+concurrency]
            print(f"\nBatch {i//concurrency + 1}: Testing {len(batch)} requests...")
            
            tasks = [make_request(session, query) for query in batch]
            batch_results = await asyncio.gather(*tasks)
            
            for result in batch_results:
                if result.success:
                    print(f"  ✓ {result.query[:40]:40s} {result.response_time:.2f}s")
                else:
                    print(f"  ✗ {result.query[:40]:40s} Failed")
            
            results.extend(batch_results)
            
            # Delay between batches
            if i + concurrency < len(queries):
                await asyncio.sleep(1)
    
    return results

def analyze_results(results: List[RequestResult], test_name: str):
    """Analyze and print statistics for results."""
    print(f"\n" + "="*60)
    print(f"ANALYSIS: {test_name}")
    print("="*60)
    
    successful = [r for r in results if r.success]
    failed = [r for r in results if not r.success]
    
    if not successful:
        print("❌ No successful requests!")
        return
    
    response_times = [r.response_time for r in successful]
    
    print(f"\n📊 Success Rate:")
    print(f"  Successful: {len(successful)}/{len(results)} ({len(successful)/len(results)*100:.1f}%)")
    print(f"  Failed:     {len(failed)}/{len(results)}")
    
    print(f"\n⏱️  Response Times:")
    print(f"  Min:     {min(response_times):.2f}s")
    print(f"  Max:     {max(response_times):.2f}s")
    print(f"  Average: {statistics.mean(response_times):.2f}s")
    print(f"  Median:  {statistics.median(response_times):.2f}s")
    if len(response_times) > 1:
        print(f"  StdDev:  {statistics.stdev(response_times):.2f}s")
    
    # Percentiles
    sorted_times = sorted(response_times)
    p50 = sorted_times[len(sorted_times)//2]
    p90 = sorted_times[int(len(sorted_times)*0.9)]
    p95 = sorted_times[int(len(sorted_times)*0.95)]
    
    print(f"\n📈 Percentiles:")
    print(f"  P50: {p50:.2f}s")
    print(f"  P90: {p90:.2f}s")
    print(f"  P95: {p95:.2f}s")
    
    # Cache effectiveness (detect fast responses)
    fast_responses = [r for r in successful if r.response_time < 2.0]
    if fast_responses:
        print(f"\n⚡ Cache Hits (< 2s):")
        print(f"  Count: {len(fast_responses)}/{len(successful)} ({len(fast_responses)/len(successful)*100:.1f}%)")
        for r in fast_responses:
            print(f"    • {r.query[:50]:50s} {r.response_time:.2f}s")
    
    # Errors
    if failed:
        print(f"\n❌ Errors:")
        for r in failed:
            print(f"  • {r.query[:40]:40s} {r.error}")
    
    # Rate limit recommendation
    avg_time = statistics.mean(response_times)
    max_time = max(response_times)
    
    print(f"\n🎯 Rate Limit Recommendations:")
    print(f"  Conservative (based on P95): {60/p95:.1f} req/min ({60/p95/60:.2f} req/sec)")
    print(f"  Moderate (based on avg):     {60/avg_time:.1f} req/min ({60/avg_time/60:.2f} req/sec)")
    print(f"  Aggressive (based on min):   {60/min(response_times):.1f} req/min ({60/min(response_times)/60:.2f} req/sec)")
    
    print(f"\n💡 Recommendations:")
    if avg_time < 3:
        print("  ✓ Excellent performance! Can handle high load.")
    elif avg_time < 6:
        print("  ✓ Good performance. Suitable for production.")
    elif avg_time < 10:
        print("  ⚠️  Moderate performance. Consider optimization.")
    else:
        print("  ⚠️  Slow performance. Optimization strongly recommended.")
    
    if len(fast_responses) / len(successful) > 0.3:
        print("  ✓ Cache is working well!")
    else:
        print("  ℹ️  Cache hit rate is low (expected for diverse queries)")

async def main():
    """Run all benchmark tests."""
    print("\n" + "🚀"*30)
    print("VIJIL DOCS AGENT BENCHMARK")
    print("🚀"*30)
    print(f"\nTarget: {BASE_URL}")
    print(f"Model: {MODEL}")
    print(f"Total queries: {len(TEST_QUERIES)}")
    print(f"Unique queries: {len(set(TEST_QUERIES))}")
    
    # Test 1: Sequential (baseline)
    sequential_results = await run_sequential_test(TEST_QUERIES)
    analyze_results(sequential_results, "Sequential Test")
    
    # Test 2: Concurrent (2 at a time)
    concurrent_2_results = await run_concurrent_test(TEST_QUERIES, concurrency=2)
    analyze_results(concurrent_2_results, "Concurrent Test (2)")
    
    # Test 3: Concurrent (3 at a time) - stress test
    concurrent_3_results = await run_concurrent_test(TEST_QUERIES, concurrency=3)
    analyze_results(concurrent_3_results, "Concurrent Test (3)")
    
    # Summary comparison
    print("\n" + "="*60)
    print("SUMMARY COMPARISON")
    print("="*60)
    
    def avg_time(results):
        successful = [r for r in results if r.success]
        return statistics.mean([r.response_time for r in successful]) if successful else 0
    
    print(f"\nAverage Response Times:")
    print(f"  Sequential:      {avg_time(sequential_results):.2f}s")
    print(f"  Concurrent (2):  {avg_time(concurrent_2_results):.2f}s")
    print(f"  Concurrent (3):  {avg_time(concurrent_3_results):.2f}s")
    
    print("\n" + "="*60)
    print("BENCHMARK COMPLETE")
    print("="*60)
    print("\nNext steps:")
    print("1. Review cache effectiveness (look for fast repeat queries)")
    print("2. Check if concurrent requests slow down significantly")
    print("3. Set rate limits based on P95 recommendations")
    print("4. Monitor your LLM provider's rate limits")
    print()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Benchmark interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Benchmark failed: {e}")
        import traceback
        traceback.print_exc()

