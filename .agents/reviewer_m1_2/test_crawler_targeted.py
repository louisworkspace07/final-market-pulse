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

# 3. Test _get_db_metrics() directly
stats_d, db_d, fresh_d = app._get_db_metrics()
print("db_d:", db_d)
print("fresh_d:", fresh_d)
assert db_d["companies"] > 0
assert fresh_d["price"] is not None

# 4. Concurrency stress test: 50 threads hammering _get_db_metrics and /stats
errors = []
def worker(wid):
    try:
        for _ in range(20):
            r = client.get("/stats")
            if r.status_code != 200:
                errors.append(f"Thread {wid} failed status {r.status_code}")
            s, d, f = app._get_db_metrics()
            if not s or not d or not f:
                errors.append(f"Thread {wid} got empty metrics")
    except Exception as ex:
        errors.append(f"Thread {wid} exception: {ex}")

threads = [threading.Thread(target=worker, args=(i,)) for i in range(50)]
t0 = time.perf_counter()
for th in threads: th.start()
for th in threads: th.join()
t_conc = (time.perf_counter() - t0) * 1000
print(f"50 concurrent threads completed in {t_conc:.2f}ms, errors={len(errors)}")
assert len(errors) == 0

# 5. Test Stale-While-Revalidate on DB error
orig_db = app.DB_PATH
try:
    from pathlib import Path
    app.DB_PATH = Path("non_existent_db_path_12345.db")
    app._METRICS_CACHE["ts"] = 0.0 # expire cache
    st, db, fr = app._get_db_metrics()
    assert st == data_stats
    print("Stale-while-revalidate fallback verified successfully!")
finally:
    app.DB_PATH = orig_db

print("ALL TARGETED CRAWLER TESTS PASSED!")
