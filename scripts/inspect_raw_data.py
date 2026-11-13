import sqlite3
import json
import urllib.request
import os

DB_PATH = r"C:\Users\toans\Desktop\Final Market Pulse\data-crawler\database\market.db"
SYMBOLS = ["FPT", "VNM", "HPG", "SSI", "MBB"]

def inspect():
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    
    print("=== INSPECTING RAW FINANCIALS FOR SYMBOLS ===")
    for sym in SYMBOLS:
        print(f"\n--- {sym} ---")
        comp = con.execute("SELECT symbol, organ_name, exchange, sector, market_cap, current_price FROM companies WHERE symbol=?", (sym,)).fetchone()
        print("Company:", comp)
        
        # Check annual financial periods
        periods = con.execute("""
            SELECT DISTINCT period FROM financials 
            WHERE symbol=? AND length(period)=4 
            ORDER BY period DESC LIMIT 5
        """, (sym,)).fetchall()
        print("Annual periods available:", [p[0] for p in periods])
        
        # Check available items in latest year
        if periods:
            latest_y = periods[0][0]
            items = con.execute("""
                SELECT item_en, value FROM financials 
                WHERE symbol=? AND period=? AND value IS NOT NULL
                ORDER BY item_en
            """, (sym, latest_y)).fetchall()
            print(f"Items in {latest_y}: {len(items)} items")
            item_dict = {i[0]: i[1] for i in items}
            for key in ["TOTAL ASSETS", "Total Assets", "Liabilities", "CURRENT ASSETS", "Current liabilities", "OWNER'S EQUITY", "Retained Earnings", "EBIT", "Net profit/(loss) after tax", "Net sales", "Gross Profit", "Net cash inflows/(outflows) from operating activities", "Net cash from operating activities"]:
                if key in item_dict:
                    print(f"  - {key}: {item_dict[key]:,.0f}")
        
        # Query API /api/stock/<sym>
        try:
            url1 = f"http://127.0.0.1:9999/api/stock/{sym}"
            res1 = json.loads(urllib.request.urlopen(url1).read())
            print(f"API /api/stock/{sym}:")
            h = res1.get("health", {})
            print(f"  health: z_score={h.get('z_score')}, z_zone={h.get('z_zone')}, f_score={h.get('f_score')}/{h.get('f_max')}, roa={h.get('roa')}, roe={h.get('roe')}")
            p = res1.get("peers", {})
            if p and "self" in p:
                print(f"  peers.self: pe={p['self'].get('pe')}, pb={p['self'].get('pb')}, roe={p['self'].get('roe')}")
        except Exception as e:
            print(f"API /api/stock/{sym} error: {e}")
            
        # Query API /api/stock/<sym>/analysis
        try:
            url2 = f"http://127.0.0.1:9999/api/stock/{sym}/analysis"
            res2 = json.loads(urllib.request.urlopen(url2).read())
            print(f"API /api/stock/{sym}/analysis:")
            val = res2.get("valuation", {})
            print(f"  valuation.pe: {val.get('pe')}")
            if "self" in val:
                print(f"  valuation.self: pe={val['self'].get('pe')}, pb={val['self'].get('pb')}, roe={val['self'].get('roe')}")
        except Exception as e:
            print(f"API /api/stock/{sym}/analysis error: {e}")

    con.close()

if __name__ == "__main__":
    inspect()
