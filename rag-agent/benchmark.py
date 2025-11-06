#!/usr/bin/env python3
"""
Benchmark script for Vijil Docs Agent
Tests response times at different RPM (requests per minute) rates
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
# BASE_URL = "https://22b30e8e1b01d732e7dae67d7b0c2dfd67dfeb53-8000.dstack-pha-prod7.phala.network/v1/chat/completions"
MODEL = "vijil-docs-agent"

# Test queries (includes duplicates to test for any caching/optimization benefits)
TEST_QUERIES = [
    "What is Vijil?",
    "How do I use Vijil for evaluation?",
    "What are Vijil's main features?",
    "What is Vijil?",  # Duplicate to test if repeated queries are faster
    "Explain Vijil detectors",
    "How does Vijil evaluate LLMs?",
    "What trust dimensions does Vijil support?",
    "What is Vijil?",  # Another duplicate
    "How do I get started with Vijil?",
    "What is the Vijil SDK?",
    "How do I install Vijil?",
    "What models does Vijil support?",
    "How do I use Vijil for evaluation?",  # Duplicate
    "What are Vijil's main features?",  # Duplicate
]

# RPM test configurations
RPM_TESTS = [10, 20, 50]  # Requests per minute to test
REQUESTS_PER_TEST = 30  # Number of requests to send per RPM test

@dataclass
class RequestResult:
    query: str
    response_time: float
    success: bool
    error: str = None
    cached: bool = False
    response_length: int = 0
    request_start_time: float = 0  # When the request was initiated

async def make_request(session: aiohttp.ClientSession, query: str, request_start_time: float = None) -> RequestResult:
    """Make a single chat completion request."""
    start_time = time.time()
    if request_start_time is None:
        request_start_time = start_time
    
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
                    response_length=len(content),
                    request_start_time=request_start_time
                )
            else:
                error_text = await response.text()
                return RequestResult(
                    query=query,
                    response_time=elapsed,
                    success=False,
                    error=f"HTTP {response.status}: {error_text[:100]}",
                    request_start_time=request_start_time
                )
    except Exception as e:
        elapsed = time.time() - start_time
        return RequestResult(
            query=query,
            response_time=elapsed,
            success=False,
            error=str(e),
            request_start_time=request_start_time
        )

async def run_rpm_test(rpm: int, num_requests: int, queries: List[str]) -> List[RequestResult]:
    """Run requests at a specific RPM (requests per minute) rate.
    
    Args:
        rpm: Target requests per minute
        num_requests: Total number of requests to make
        queries: List of query strings to cycle through
    """
    print(f"\n" + "="*60)
    print(f"RPM TEST: {rpm} requests/minute")
    print("="*60)
    print(f"Target: {num_requests} total requests")
    print(f"Expected duration: {num_requests / rpm:.1f} minutes ({num_requests * 60 / rpm:.0f} seconds)")
    
    # Calculate delay between requests to achieve target RPM
    delay_between_requests = 60.0 / rpm
    print(f"Delay between requests: {delay_between_requests:.2f}s")
    
    results = []
    test_start = time.time()
    
    async with aiohttp.ClientSession() as session:
        for i in range(num_requests):
            # Cycle through queries
            query = queries[i % len(queries)]
            
            # Schedule next request time
            target_time = test_start + (i * delay_between_requests)
            current_time = time.time()
            
            # Wait if we're ahead of schedule
            if current_time < target_time:
                await asyncio.sleep(target_time - current_time)
            
            # Make request (don't await, start it and continue)
            request_start = time.time()
            
            # Start request as background task
            result = await make_request(session, query, request_start)
            results.append(result)
            
            # Progress indicator
            elapsed = time.time() - test_start
            actual_rpm = (i + 1) / (elapsed / 60) if elapsed > 0 else 0
            
            status = "✓" if result.success else "✗"
            print(f"[{i+1}/{num_requests}] {status} {result.response_time:.2f}s | "
                  f"Actual RPM: {actual_rpm:.1f} | "
                  f"Elapsed: {elapsed:.0f}s")
    
    total_duration = time.time() - test_start
    actual_rpm = num_requests / (total_duration / 60)
    
    print(f"\n📊 Test Complete:")
    print(f"  Duration: {total_duration:.1f}s ({total_duration/60:.2f} min)")
    print(f"  Target RPM: {rpm}")
    print(f"  Actual RPM: {actual_rpm:.1f}")
    print(f"  RPM Accuracy: {(actual_rpm/rpm)*100:.1f}%")
    
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
        if failed:
            print(f"\n❌ Errors ({len(failed)} total):")
            for r in failed[:5]:  # Show first 5
                print(f"  • {r.query[:40]:40s} {r.error}")
            if len(failed) > 5:
                print(f"  ... and {len(failed)-5} more errors")
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
    p99 = sorted_times[int(len(sorted_times)*0.99)] if len(sorted_times) > 10 else sorted_times[-1]
    
    print(f"\n📈 Percentiles:")
    print(f"  P50 (median): {p50:.2f}s")
    print(f"  P90:          {p90:.2f}s")
    print(f"  P95:          {p95:.2f}s")
    print(f"  P99:          {p99:.2f}s")
    
    # Errors
    if failed:
        print(f"\n❌ Errors ({len(failed)} total):")
        for r in failed[:3]:  # Show first 3
            print(f"  • {r.query[:40]:40s} {r.error[:50]}")
        if len(failed) > 3:
            print(f"  ... and {len(failed)-3} more errors")
    
    # Performance assessment
    avg_time = statistics.mean(response_times)
    
    print(f"\n💡 Performance Assessment:")
    if avg_time < 3:
        print("  ✓ Excellent! Can handle high load.")
    elif avg_time < 6:
        print("  ✓ Good. Suitable for production.")
    elif avg_time < 10:
        print("  ⚠️  Moderate. Consider optimization.")
    else:
        print("  ⚠️  Slow. Optimization strongly recommended.")
    
    # Can system sustain this rate?
    if len(failed) == 0:
        print(f"  ✓ System sustained this load successfully!")
    elif len(failed) / len(results) < 0.05:
        print(f"  ⚠️  Minor issues ({len(failed)/len(results)*100:.1f}% failure rate)")
    else:
        print(f"  ❌ Significant failures ({len(failed)/len(results)*100:.1f}% failure rate)")
    
    # Rate limit suggestions based on results
    print(f"\n🎯 Rate Limit Suggestions:")
    print(f"  Conservative (P95): ~{int(60/p95)} RPM")
    print(f"  Moderate (avg):     ~{int(60/avg_time)} RPM")
    print(f"  Aggressive (P50):   ~{int(60/p50)} RPM")

async def main():
    """Run all benchmark tests."""
    print("\n" + "🚀"*30)
    print("VIJIL DOCS AGENT RPM BENCHMARK")
    print("🚀"*30)
    print(f"\nTarget: {BASE_URL}")
    print(f"Model: {MODEL}")
    print(f"Test queries pool: {len(TEST_QUERIES)} unique queries")
    print(f"RPM rates to test: {', '.join(map(str, RPM_TESTS))}")
    print(f"Requests per test: {REQUESTS_PER_TEST}")
    
    all_results = {}
    
    # Run tests for each RPM rate
    for rpm in RPM_TESTS:
        print(f"\n{'='*60}")
        print(f"Starting {rpm} RPM test...")
        print(f"{'='*60}")
        
        results = await run_rpm_test(rpm, REQUESTS_PER_TEST, TEST_QUERIES)
        all_results[rpm] = results
        
        # Analyze immediately after each test
        analyze_results(results, f"{rpm} RPM Test")
        
        # Brief cooldown between tests
        if rpm != RPM_TESTS[-1]:  # Don't wait after last test
            print(f"\n⏸️  Cooldown: 10 seconds before next test...")
            await asyncio.sleep(10)
    
    # Summary comparison
    print("\n" + "="*60)
    print("SUMMARY COMPARISON")
    print("="*60)
    
    def get_stats(results):
        successful = [r for r in results if r.success]
        if not successful:
            return None
        times = [r.response_time for r in successful]
        return {
            'avg': statistics.mean(times),
            'p50': statistics.median(times),
            'p95': sorted(times)[int(len(times)*0.95)],
            'success_rate': len(successful) / len(results) * 100
        }
    
    print("\n" + "-"*60)
    print(f"{'RPM':<10} {'Avg Time':<12} {'P50':<10} {'P95':<10} {'Success Rate':<15}")
    print("-"*60)
    
    for rpm in RPM_TESTS:
        stats = get_stats(all_results[rpm])
        if stats:
            print(f"{rpm:<10} {stats['avg']:<12.2f}s {stats['p50']:<10.2f}s "
                  f"{stats['p95']:<10.2f}s {stats['success_rate']:<15.1f}%")
        else:
            print(f"{rpm:<10} {'FAILED':<12} {'N/A':<10} {'N/A':<10} {'0.0%':<15}")
    
    print("-"*60)
    
    # Recommendations
    print("\n" + "="*60)
    print("RECOMMENDATIONS")
    print("="*60)
    
    sustainable_rpms = []
    for rpm in RPM_TESTS:
        stats = get_stats(all_results[rpm])
        if stats and stats['success_rate'] >= 95 and stats['p95'] < 10:
            sustainable_rpms.append(rpm)
    
    if sustainable_rpms:
        max_sustainable = max(sustainable_rpms)
        print(f"\n✅ Highest sustainable rate: {max_sustainable} RPM")
        print(f"   (≥95% success rate, P95 < 10s)")
    else:
        print(f"\n⚠️  No rate achieved 95% success with P95 < 10s")
        print(f"   Consider:")
        print(f"   - Scaling infrastructure")
        print(f"   - Optimizing agent/tools")
        print(f"   - Reducing max_tokens")
    
    print("\n" + "="*60)
    print("BENCHMARK COMPLETE")
    print("="*60)
    print(f"\nTotal requests sent: {sum(len(r) for r in all_results.values())}")
    print(f"Total test duration: Check logs above for per-test durations")
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

