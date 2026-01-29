import time
import datetime
import random
import sys

def benchmark():
    # Generate mock data
    N = 10000
    cases = []
    base_time = datetime.datetime.now()

    print(f"Generating {N} mock cases...")
    for i in range(N):
        dt = base_time - datetime.timedelta(minutes=random.randint(0, 100000))
        iso_str = dt.isoformat()
        cases.append({
            "case_id": f"case_{i}",
            "updated": iso_str,
            "_updated_ts": dt.timestamp()
        })

    # Benchmark Old Method
    def _parse_time(t):
        if not t: return 0.0
        try:
            return datetime.datetime.fromisoformat(str(t)).timestamp()
        except ValueError:
            return 0.0

    print("Benchmarking old method (datetime.fromisoformat inside sort)...")
    start_time = time.perf_counter()
    sorted_old = sorted(cases, key=lambda x: _parse_time(x.get("updated")), reverse=True)
    end_time = time.perf_counter()
    old_duration = end_time - start_time
    print(f"Old method took: {old_duration:.4f} seconds")

    # Benchmark New Method
    print("Benchmarking new method (using pre-calculated _updated_ts)...")
    start_time = time.perf_counter()
    sorted_new = sorted(cases, key=lambda x: x.get("_updated_ts", 0.0), reverse=True)
    end_time = time.perf_counter()
    new_duration = end_time - start_time
    print(f"New method took: {new_duration:.4f} seconds")

    # Verify Correctness
    print("Verifying correctness...")
    ids_old = [c["case_id"] for c in sorted_old]
    ids_new = [c["case_id"] for c in sorted_new]

    if ids_old == ids_new:
        print("SUCCESS: Both methods produced the same order.")
    else:
        print("FAILURE: Methods produced different orders.")
        # Check first mismatch
        for i in range(len(ids_old)):
            if ids_old[i] != ids_new[i]:
                print(f"Mismatch at index {i}: Old={ids_old[i]}, New={ids_new[i]}")
                break
        sys.exit(1)

    speedup = old_duration / new_duration if new_duration > 0 else 0
    print(f"Speedup: {speedup:.2f}x")

if __name__ == "__main__":
    benchmark()
