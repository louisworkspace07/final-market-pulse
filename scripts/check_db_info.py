import sqlite3

db_path = 'data-crawler/database/market.db'
conn = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)

# 1. Check indexes on price
indexes = conn.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='price'").fetchall()
print("=== INDEXES ON price ===")
for name, sql in indexes:
    print(f"  {name}: {sql}")

# 2. Check symbols with < 60 bars in market.db
print("\n=== SYMBOLS WITH 0 < BARS < 60 ===")
cur = conn.execute("""
    SELECT symbol, count(*) as cnt 
    FROM price 
    WHERE close IS NOT NULL 
    GROUP BY symbol 
    HAVING cnt > 0 AND cnt < 60 
    ORDER BY cnt ASC 
    LIMIT 10
""")
symbols_under_60 = cur.fetchall()
for sym, cnt in symbols_under_60:
    print(f"  {sym}: {cnt} bars")

# 3. Check symbols with >= 60 bars
cur = conn.execute("""
    SELECT symbol, count(*) as cnt 
    FROM price 
    WHERE close IS NOT NULL 
    GROUP BY symbol 
    HAVING cnt >= 60 
    ORDER BY cnt DESC 
    LIMIT 5
""")
print("\n=== TOP SYMBOLS WITH BARS >= 60 ===")
for sym, cnt in cur.fetchall():
    print(f"  {sym}: {cnt} bars")

conn.close()
