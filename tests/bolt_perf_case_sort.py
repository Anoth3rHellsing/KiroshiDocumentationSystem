import time
import datetime
import random
import statistics

def _parse_time_orig(t):
    if not t: return 0.0
    try:
        return datetime.datetime.fromisoformat(str(t)).timestamp()
    except ValueError:
        return 0.0

def benchmark_sort():
    # Generate mock data
    print("Generating mock data...")
    items = []
    now = datetime.datetime.now()
    for i in range(10000):
        dt = now - datetime.timedelta(minutes=random.randint(0, 100000))
        iso = dt.isoformat()
        ts = dt.timestamp()
        items.append({
            "updated": iso,
            "_updated_ts": ts,
            "data": f"some data {i}"
        })

    # Measure original sort
    print("Benchmarking original sort...")
    times_orig = []
    for _ in range(50):
        test_data = items.copy()
        start = time.perf_counter()
        test_data.sort(key=lambda x: _parse_time_orig(x.get("updated")), reverse=True)
        end = time.perf_counter()
        times_orig.append(end - start)

    avg_orig = statistics.mean(times_orig)
    print(f"Original sort average time: {avg_orig*1000:.4f} ms")

    # Measure optimized sort
    print("Benchmarking optimized sort...")
    times_opt = []
    for _ in range(50):
        test_data = items.copy()
        start = time.perf_counter()
        test_data.sort(key=lambda x: x.get("_updated_ts", 0.0), reverse=True)
        end = time.perf_counter()
        times_opt.append(end - start)

    avg_opt = statistics.mean(times_opt)
    print(f"Optimized sort average time: {avg_opt*1000:.4f} ms")

    speedup = avg_orig / avg_opt
    print(f"Speedup: {speedup:.2f}x")

if __name__ == "__main__":
    benchmark_sort()
