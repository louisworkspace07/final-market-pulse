import time, os, sys, sqlite3
sys.path.insert(0, os.getcwd())

# Force UTF-8 stdout
sys.stdout.reconfigure(encoding='utf-8')

db_path = os.path.join(os.getcwd(), '..', 'data-crawler', 'database', 'market.db')
print("DB Exists:", os.path.exists(db_path))

from collections import defaultdict, namedtuple
PriceRow = namedtuple('PriceRow', ['symbol', 'time', 'open', 'high', 'low', 'close', 'volume'])

t0 = time.time()
con = sqlite3.connect(db_path)
cursor = con.execute("SELECT symbol, time, open, high, low, close, volume FROM price ORDER BY symbol, time")
by_sym = defaultdict(list)
for row in map(PriceRow._make, cursor):
    by_sym[row.symbol].append(row)
con.close()
t1 = time.time()
print(f"Load & Group DB (NamedTuple): {t1 - t0:.2f}s")
sys.exit(0)

t2 = time.time()
print(f"Group rows: {t2 - t1:.2f}s")

vol_by_sym = {}
signals = []
as_of = None

for sym, rows in by_sym.items():
    limit_pct = _LIMIT_BY_EXCHANGE.get(exch.get(sym, ""), _DEFAULT_LIMIT)
    sigs = _detect_symbol_optimized(sym, rows, news_days.get(sym, set()), sym in covered, limit_pct)
    last_time = str(rows[-1].time)
    vol_by_sym[(sym, last_time[:10])] = float(rows[-1].volume)
    if sigs:
        signals.extend(sigs)
        as_of = max(as_of or "", last_time)

t3 = time.time()
print(f"Detect signals: {t3 - t2:.2f}s")

_assign_severity(signals)

t4 = time.time()
print(f"Assign severity: {t4 - t3:.2f}s")

_rss_backfill(signals, names)

t5 = time.time()
print(f"RSS backfill: {t5 - t4:.2f}s")

fx = _detect_foreign_flip(vol_by_sym, [], "2026-08-09")

t6 = time.time()
print(f"Detect foreign flip: {t6 - t5:.2f}s")
print(f"Total time: {t6 - t0:.2f}s")
