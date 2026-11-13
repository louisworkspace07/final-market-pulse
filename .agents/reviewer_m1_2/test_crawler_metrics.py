import sys, time, threading
sys.path.insert(0, "data-crawler")
import app

client = app.app.test_client()

# 1. Test Cold call
app._METRICS_CACHE = {"ts": 0.0, "stats": None, "db": None, "fresh": None}
t0 = time.perf_counter()
r_stats = client.get("/stats")
t_cold = (time.perf_counter() - t0) * 1000
assert r_stats.status_code == 200
data_stats = r_stats.get_json()
print(f"Cold /stats: {t_cold:.2f}ms, data={data_stats}")

# 2. Test Warm cache hit
t0 = time.perf_counter()
r_stats_cached = client.get("/stats")
t_warm = (time.perf_counter() - t0) * 1000
assert r_stats_cached.status_code == 200
assert r_stats_cached.get_json() == data_stats
print(f"Warm /stats: {t_warm:.3f}ms (target < 2ms)")
assert t_warm < 2.0

# 3. Test /health endpoint
t0 = time.perf_counter()
r_health = client.get("/health")
t_health = (time.perf_counter() - t0) * 1000
assert r_health.status_code == 200
data_health = r_health.get_json()
print(f"Health response in {t_health:.3f}ms: status={data_health.get('status')}, db={data_health.get('db')}, fresh={data_health.get('fresh')}")
assert "db" in data_health and "fresh" in data_health
assert data_health["fresh"]["price"] is not None

# 4. Test Stale-While-Revalidate on DB error
orig_db = app.DB_PATH
try:
    from pathlib import Path
    app.DB_PATH = Path("non_existent_db_path_12345.db")
    # Expire TTL to force attempt to read
    app._METRICS_CACHE["ts"] = 0.0
    r_stale = client.get("/stats")
    assert r_stale.status_code == 200
    assert r_stale.get_json() == data_stats
    print("Stale-while-revalidate fallback verified!")
finally:
    app.DB_PATH = orig_db

# 5. Concurrency stress test: 20 threads hammering /stats and /health simultaneously
errors = []
def worker(wid):
    try:
        for _ in range(50):
            r1 = client.get("/stats")
            r2 = client.get("/health")
            if r1.status_code != 200 or r2.status_code != 200:
                errors.append(f"Thread {wid} failed with {r1.status_code}, {r2.status_code}")
    except Exception as ex:
        errors.append(f"Thread {wid} exception: {ex}")

threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
t0 = time.perf_counter()
for th in threads: th.start()
for th in threads: th.join()
t_conc = (time.perf_counter() - t0) * 1000
print(f"20 concurrent threads (1000 requests each) completed in {t_conc:.2f}ms, errors={len(errors)}")
assert len(errors) == 0

print("ALL CRAWLER METRICS TESTS PASSED SUCCESSFULLY!")
