"""
Concurrency stress test for data-crawler /stats and /health endpoints.
Verifies that 20 concurrent threads polling endpoints do not encounter
sqlite3.OperationalError: database is locked, even under high concurrency
and simulated database write activity.
"""
import sys
import time
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Add data-crawler root to sys.path
CRAWLER_DIR = Path(__file__).resolve().parent.parent
if str(CRAWLER_DIR) not in sys.path:
    sys.path.insert(0, str(CRAWLER_DIR))

import app

def test_20_concurrent_threads_cold_cache():
    """Simulate 20 concurrent threads requesting /stats with cold cache."""
    app._METRICS_CACHE["ts"] = 0.0
    app._METRICS_CACHE["stats"] = None
    app._METRICS_CACHE["db"] = None
    app._METRICS_CACHE["fresh"] = None

    client = app.app.test_client()
    num_threads = 20
    errors = []
    statuses = []

    def poll_stats(thread_id):
        try:
            r = client.get('/stats')
            return r.status_code, r.get_json(), None
        except Exception as e:
            return None, None, e

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(poll_stats, i) for i in range(num_threads)]
        for f in as_completed(futures):
            status, data, err = f.result()
            if err:
                errors.append(err)
            else:
                statuses.append(status)
                if data:
                    assert "companies" in data

    assert len(errors) == 0, f"Encountered errors: {errors}"
    assert all(s == 200 for s in statuses)
    assert len(statuses) == num_threads


def test_20_concurrent_threads_polling_stats_and_health():
    """Simulate 20 concurrent threads heavily polling /stats and /health in parallel."""
    client = app.app.test_client()
    num_threads = 20
    iterations_per_thread = 25  # 500 total requests
    errors = []

    def worker_poll(thread_id):
        thread_errors = []
        for i in range(iterations_per_thread):
            endpoint = '/stats' if (i % 2 == 0) else '/health'
            try:
                r = client.get(endpoint)
                if r.status_code != 200:
                    thread_errors.append(f"HTTP {r.status_code} on {endpoint}")
                data = r.get_json()
                if not data:
                    thread_errors.append(f"Empty data from {endpoint}")
            except Exception as e:
                thread_errors.append(f"Exception on {endpoint}: {type(e).__name__}: {e}")
            time.sleep(0.005)
        return thread_errors

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker_poll, i) for i in range(num_threads)]
        for f in as_completed(futures):
            res = f.result()
            errors.extend(res)

    assert len(errors) == 0, f"Encountered polling errors: {errors}"


def test_concurrency_with_active_db_writes():
    """Simulate 20 concurrent readers while a background writer writes to market.db."""
    client = app.app.test_client()
    num_readers = 20
    stop_event = threading.Event()
    writer_errors = []
    reader_errors = []

    db_path = app.DB_PATH

    # Background writer simulating crawl state updates
    def background_writer():
        try:
            conn = sqlite3.connect(str(db_path), timeout=10)
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS _concurrency_stress_test (
                    id INTEGER PRIMARY KEY,
                    val TEXT,
                    ts REAL
                )
            """)
            conn.commit()

            count = 0
            while not stop_event.is_set():
                cur.execute("BEGIN IMMEDIATE")
                cur.execute(
                    "INSERT INTO _concurrency_stress_test (val, ts) VALUES (?, ?)",
                    (f"stress_{count}", time.time())
                )
                time.sleep(0.05)  # hold write transaction for 50ms
                conn.commit()
                count += 1
                time.sleep(0.01)

            # Cleanup
            cur.execute("DROP TABLE IF EXISTS _concurrency_stress_test")
            conn.commit()
            conn.close()
        except Exception as e:
            writer_errors.append(f"Writer error: {type(e).__name__}: {e}")

    # Start writer thread
    writer_thread = threading.Thread(target=background_writer, daemon=True)
    writer_thread.start()

    # Readers polling /stats and /health
    def reader_task(reader_id):
        thread_errors = []
        for i in range(20):
            endpoint = '/stats' if i % 2 == 0 else '/health'
            try:
                # Invalidate cache periodically to force DB hits during active writes
                if i % 5 == 0:
                    app._METRICS_CACHE["ts"] = 0.0
                r = client.get(endpoint)
                if r.status_code != 200:
                    thread_errors.append(f"Reader {reader_id} HTTP {r.status_code}")
            except Exception as e:
                thread_errors.append(f"Reader {reader_id} {type(e).__name__}: {e}")
            time.sleep(0.01)
        return thread_errors

    try:
        with ThreadPoolExecutor(max_workers=num_readers) as executor:
            futures = [executor.submit(reader_task, i) for i in range(num_readers)]
            for f in as_completed(futures):
                reader_errors.extend(f.result())
    finally:
        stop_event.set()
        writer_thread.join(timeout=5)

    assert len(writer_errors) == 0, f"Writer errors: {writer_errors}"
    assert len(reader_errors) == 0, f"Reader errors under write lock: {reader_errors}"


if __name__ == "__main__":
    print("Running test 1: 20 concurrent threads cold cache...")
    test_20_concurrent_threads_cold_cache()
    print("Test 1 PASSED.")

    print("Running test 2: 20 concurrent threads polling stats & health...")
    test_20_concurrent_threads_polling_stats_and_health()
    print("Test 2 PASSED.")

    print("Running test 3: 20 concurrent readers with active background writer...")
    test_concurrency_with_active_db_writes()
    print("Test 3 PASSED.")
    print("All concurrency stress tests PASSED successfully!")
