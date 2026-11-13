import sqlite3
import time
import sys

con = sqlite3.connect('data-crawler/database/market.db')
cur = con.execute("SELECT sql FROM sqlite_master WHERE name='idx_price_time'")
print('Index SQL:', cur.fetchone())

t0 = time.perf_counter()
plan = con.execute("EXPLAIN QUERY PLAN SELECT max(time) FROM price").fetchall()
t1 = time.perf_counter()
print('Query Plan:', plan)
print(f'Plan check elapsed: {(t1-t0)*1000:.3f}ms')
assert any('idx_price_time' in str(row) for row in plan)

t0 = time.perf_counter()
res = con.execute("SELECT max(time) FROM price").fetchone()
t1 = time.perf_counter()
print(f'Max time: {res[0]} in {(t1-t0)*1000:.3f}ms')
assert (t1-t0)*1000 < 5.0

print('Index verification SUCCESSFUL!')
