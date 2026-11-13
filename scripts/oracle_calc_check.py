import sqlite3
import json

DB_PATH = r"C:\Users\toans\Desktop\Final Market Pulse\data-crawler\database\market.db"

ITEMS_MAP = {
    "total_assets": ["TOTAL ASSETS", "Total Assets"],
    "liabilities": ["Liabilities"],
    "current_assets": ["CURRENT ASSETS"],
    "current_liab": ["Current liabilities"],
    "equity": ["OWNER'S EQUITY", "Owner's Equity", "Owners Equity"],
    "retained": ["Retained Earnings", "Retained earnings"],
    "ebit": ["EBIT"],
    "net_income": ["Net profit/(loss) after tax"],
    "revenue": ["Net sales"],
    "gross_profit": ["Gross Profit"],
    "cfo": ["Net cash inflows/(outflows) from operating activities",
            "Net cash from operating activities"],
}

def get_item(fin_rows, year, key):
    aliases = ITEMS_MAP[key]
    for r in fin_rows:
        if r["period"] == str(year) and r["item_en"] in aliases:
            return r["value"]
    return None

def main():
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    symbols = ["FPT", "VNM", "HPG", "SSI", "MBB"]
    
    for sym in symbols:
        print(f"\n==================== {sym} ====================")
        rows = con.execute("""
            SELECT statement, item_id, item_en, period, value 
            FROM financials 
            WHERE symbol=? AND length(period)=4 AND period >= '2023' AND value IS NOT NULL
        """, (sym,)).fetchall()
        
        years = sorted(list({int(r["period"]) for r in rows}))
        print(f"Available years: {years}")
        y1 = years[-1]
        y0 = years[-2] if len(years) >= 2 else None
        print(f"Target calculation year y1={y1}, prior year y0={y0}")
        
        ta1 = get_item(rows, y1, "total_assets")
        liab1 = get_item(rows, y1, "liabilities")
        ca1 = get_item(rows, y1, "current_assets")
        cl1 = get_item(rows, y1, "current_liab")
        eq1 = get_item(rows, y1, "equity")
        ret1 = get_item(rows, y1, "retained")
        ebit1 = get_item(rows, y1, "ebit")
        ni1 = get_item(rows, y1, "net_income")
        rev1 = get_item(rows, y1, "revenue")
        gp1 = get_item(rows, y1, "gross_profit")
        cfo1 = get_item(rows, y1, "cfo")

        print(f"Year {y1} Raw Items:")
        print(f"  Total Assets (ta): {ta1}")
        print(f"  Liabilities (liab): {liab1}")
        print(f"  Current Assets (ca): {ca1}")
        print(f"  Current Liab (cl): {cl1}")
        print(f"  Equity (eq): {eq1}")
        print(f"  Retained Earnings (ret): {ret1}")
        print(f"  EBIT (ebit): {ebit1}")
        print(f"  Net Income (ni): {ni1}")
        print(f"  Revenue (rev): {rev1}")
        print(f"  Gross Profit (gp): {gp1}")
        print(f"  CFO (cfo): {cfo1}")
        
        is_financial = (ca1 is None or cl1 is None)
        print(f"  is_financial: {is_financial}")
        
        # 1. Altman Z'' calculation
        if not is_financial and liab1 and liab1 > 0 and ta1 and ta1 > 0:
            x1 = (ca1 - cl1) / ta1
            x2 = (ret1 or 0) / ta1
            x3 = (ebit1 or 0) / ta1
            x4 = (eq1 or 0) / liab1
            z = 6.56 * x1 + 3.26 * x2 + 6.72 * x3 + 1.05 * x4
            z_zone = "An toàn" if z > 2.6 else ("Xám" if z >= 1.1 else "Nguy hiểm")
            print(f"\n[ORACLE ALTMAN Z'']")
            print(f"  X1 (WC/TA) = ({ca1} - {cl1}) / {ta1} = {x1:.6f}")
            print(f"  X2 (RE/TA) = {ret1} / {ta1} = {x2:.6f}")
            print(f"  X3 (EBIT/TA) = {ebit1} / {ta1} = {x3:.6f}")
            print(f"  X4 (EQ/TL) = {eq1} / {liab1} = {x4:.6f}")
            print(f"  Z'' = 6.56*{x1:.6f} + 3.26*{x2:.6f} + 6.72*{x3:.6f} + 1.05*{x4:.6f} = {z:.4f} -> rounded: {round(z, 2)} ({z_zone})")
        else:
            print(f"\n[ORACLE ALTMAN Z'']")
            print(f"  Z'' = None (Financial institution / Missing CA/CL)")

        # 2. ROA, ROE calculation
        roa = (ni1 / ta1 * 100.0) if (ni1 is not None and ta1) else None
        roe = (ni1 / eq1 * 100.0) if (ni1 is not None and eq1) else None
        print(f"\n[ORACLE ROA, ROE]")
        print(f"  ROA = {ni1} / {ta1} * 100 = {roa:.2f}%" if roa is not None else "  ROA = None")
        print(f"  ROE = {ni1} / {eq1} * 100 = {roe:.2f}%" if roe is not None else "  ROE = None")

        # 3. Piotroski F-score
        print(f"\n[ORACLE PIOTROSKI F-SCORE]")
        f_score = 0
        f_max = 0
        checks = []
        
        # Check 1: ROA > 0
        if roa is not None:
            f_max += 1
            passed = roa > 0
            f_score += int(passed)
            checks.append(("ROA > 0", passed))
            
        # Check 2: CFO > 0
        if cfo1 is not None:
            f_max += 1
            passed = cfo1 > 0
            f_score += int(passed)
            checks.append(("CFO > 0", passed))
            
        # Check 3: CFO > NI
        if cfo1 is not None and ni1 is not None:
            f_max += 1
            passed = cfo1 > ni1
            f_score += int(passed)
            checks.append(("CFO > NI", passed))
            
        if y0 is not None:
            ta0 = get_item(rows, y0, "total_assets")
            liab0 = get_item(rows, y0, "liabilities")
            ca0 = get_item(rows, y0, "current_assets")
            cl0 = get_item(rows, y0, "current_liab")
            ni0 = get_item(rows, y0, "net_income")
            rev0 = get_item(rows, y0, "revenue")
            gp0 = get_item(rows, y0, "gross_profit")
            roa0 = (ni0 / ta0 * 100.0) if (ni0 is not None and ta0) else None
            
            # Check 4: ROA improving
            if roa is not None and roa0 is not None:
                f_max += 1
                passed = roa > roa0
                f_score += int(passed)
                checks.append(("ROA improving", passed))
                
            # Check 5: Leverage decreasing (Liab / TA < Liab0 / TA0)
            if liab1 is not None and liab0 is not None and ta1 and ta0:
                f_max += 1
                passed = (liab1 / ta1) < (liab0 / ta0)
                f_score += int(passed)
                checks.append(("Leverage decreasing", passed))
                
            # Check 6: Liquidity improving (CA / CL > CA0 / CL0) (non-financial only)
            if not is_financial and all(v is not None for v in [ca0, cl0, ca1, cl1]) and cl1 > 0 and cl0 > 0:
                f_max += 1
                passed = (ca1 / cl1) > (ca0 / cl0)
                f_score += int(passed)
                checks.append(("Liquidity improving", passed))
                
            # Check 7: Gross Margin improving (GP / Rev > GP0 / Rev0) (non-financial only)
            if all(v is not None for v in [rev1, gp1, rev0, gp0]) and rev1 > 0 and rev0 > 0:
                f_max += 1
                passed = (gp1 / rev1) > (gp0 / rev0)
                f_score += int(passed)
                checks.append(("Gross Margin improving", passed))
                
        print(f"  F-Score = {f_score}/{f_max}")
        for label, passed in checks:
            print(f"    - {label}: {'PASS' if passed else 'FAIL'}")

    con.close()

if __name__ == "__main__":
    main()
