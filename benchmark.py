import asyncio
import time
import httpx
import statistics
from typing import List, Dict, Any
import argparse

async def benchmark_api(endpoint: str, num_requests: int = 10, concurrent: int = 5):
    """
    Benchmark the API performance
    
    Args:
        endpoint: API endpoint to benchmark
        num_requests: Total number of requests to make
        concurrent: Number of concurrent requests
    """
    print(f"Benchmarking {endpoint} with {num_requests} requests ({concurrent} concurrent)...")
    
    # Create a semaphore to limit concurrency
    semaphore = asyncio.Semaphore(concurrent)
    
    async def make_request():
        async with semaphore:
            start_time = time.time()
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.get(endpoint)
                    end_time = time.time()
                    return {
                        "status_code": response.status_code,
                        "time": end_time - start_time,
                        "success": response.status_code == 200
                    }
                except Exception as e:
                    end_time = time.time()
                    return {
                        "status_code": 0,
                        "time": end_time - start_time,
                        "success": False,
                        "error": str(e)
                    }
    
    # Make the requests
    tasks = [make_request() for _ in range(num_requests)]
    results = await asyncio.gather(*tasks)
    
    # Calculate statistics
    times = [result["time"] for result in results if result["success"]]
    success_count = sum(1 for result in results if result["success"])
    
    if not times:
        print("No successful requests")
        return
    
    # Print results
    print(f"Results for {endpoint}:")
    print(f"  Success rate: {success_count}/{num_requests} ({success_count/num_requests*100:.2f}%)")
    print(f"  Min time: {min(times):.4f}s")
    print(f"  Max time: {max(times):.4f}s")
    print(f"  Avg time: {sum(times)/len(times):.4f}s")
    print(f"  Median time: {statistics.median(times):.4f}s")
    print(f"  95th percentile: {sorted(times)[int(len(times)*0.95)]:.4f}s")
    print(f"  Requests per second: {num_requests/sum(times):.2f}")

async def main():
    parser = argparse.ArgumentParser(description="Benchmark the API performance")
    parser.add_argument("--host", default="http://localhost:12000", help="API host")
    parser.add_argument("--requests", type=int, default=100, help="Number of requests")
    parser.add_argument("--concurrent", type=int, default=10, help="Number of concurrent requests")
    args = parser.parse_args()
    
    # Benchmark the root endpoint
    await benchmark_api(f"{args.host}/", args.requests, args.concurrent)
    
    # Benchmark the API endpoints
    # Note: You would need to modify this to include actual data for POST requests
    await benchmark_api(f"{args.host}/api/v1/images/searches", args.requests, args.concurrent)

if __name__ == "__main__":
    asyncio.run(main())