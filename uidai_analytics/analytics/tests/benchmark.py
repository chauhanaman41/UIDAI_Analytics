import time
import requests
import statistics
import os

BASE_URL = os.getenv('API_URL', 'http://localhost:8000')

def benchmark_endpoint(url, iterations=20):
    times = []
    print(f"Benchmarking {url} ({iterations} iterations)...")
    success_count = 0
    for _ in range(iterations):
        start = time.time()
        try:
            resp = requests.get(url)
            if resp.status_code == 200:
                success_count += 1
            times.append(time.time() - start)
        except requests.exceptions.RequestException:
            times.append(time.time() - start)
            
    if not times:
        return {}

    return {
        'url': url,
        'iterations': iterations,
        'success_rate': f"{success_count}/{iterations}",
        'avg_ms': round(statistics.mean(times) * 1000, 2),
        'p95_ms': round(sorted(times)[int(len(times) * 0.95)] * 1000, 2),
        'max_ms': round(max(times) * 1000, 2),
        'min_ms': round(min(times) * 1000, 2)
    }

if __name__ == "__main__":
    endpoints = [
        f"{BASE_URL}/api/enrollments/trends/?state=Goa",
        f"{BASE_URL}/api/anomalies/",
        f"{BASE_URL}/api/forecasts/Delhi/",
        f"{BASE_URL}/api/biometric/success-rates/",
        f"{BASE_URL}/api/recommendations/"
    ]
    
    report = []
    print("\n--- Performance Benchmark Report ---\n")
    for ep in endpoints:
        stats = benchmark_endpoint(ep)
        print(f"  Result: {stats}")
        report.append(stats)
        
    # Analyze results
    print("\n--- Summary ---")
    slow_endpoints = [r for r in report if r['p95_ms'] > 500]
    if slow_endpoints:
        print("SLOW ENDPOINTS (>500ms p95):")
        for s in slow_endpoints:
            print(f"  - {s['url']}: {s['p95_ms']}ms")
    else:
        print("All tested endpoints are within performance targets (<500ms).")
