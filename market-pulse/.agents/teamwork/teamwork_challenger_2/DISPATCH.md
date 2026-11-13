# Dispatch for Challenger 2

## Mission
Adversarial verification of calculations and data authenticity:
- Directly query `data-crawler/database/market.db` to extract balance sheet and income statement items for sample companies (e.g. FPT, VNM, HPG, VCB).
- Re-compute Altman Z''-score and Piotroski F-score by hand/independent script using exact mathematical formulas.
- Compare independent results against API output from `/api/stock/<sym>` and `/api/stock/<sym>/analysis`. Verify exact match.
- Probe `/api/vbp/<sym>` across 20 symbols and repeat calls to verify no random numbers or hardcoded sequences are returned.
- Record findings, independent oracle calculation script, and verdict (APPROVE or REQUEST_CHANGES) in:
  `C:\Users\toans\Desktop\Final Market Pulse\market-pulse\.agents\teamwork\teamwork_challenger_2\handoff.md`

## 2026-11-13T12:53:57Z
You are Challenger 2 (Archetype: teamwork_challenger).
Your working directory is: C:\Users\toans\Desktop\Final Market Pulse\market-pulse\.agents\teamwork\teamwork_challenger_2

Read ORIGINAL_REQUEST.md at: C:\Users\toans\Desktop\Final Market Pulse\market-pulse\.agents\teamwork\ORIGINAL_REQUEST.md
Also read your task instructions at: C:\Users\toans\Desktop\Final Market Pulse\market-pulse\.agents\teamwork\teamwork_challenger_2\DISPATCH.md
Read Worker 1's handoff report at: C:\Users\toans\Desktop\Final Market Pulse\market-pulse\.agents\teamwork\teamwork_worker_remediation_1\handoff.md
And PROJECT.md at: C:\Users\toans\Desktop\Final Market Pulse\market-pulse\.agents\teamwork\orchestrator\PROJECT.md

Your Task:
Adversarially verify calculation authenticity and test for any lingering mock behavior:
1. Oracle calculation check:
   - Query `data-crawler/database/market.db` directly for balance sheet and income statement items of 5 companies (e.g., FPT, VNM, HPG, SSI, MBB).
   - Independently compute Altman Z''-score, Piotroski F-score, ROA, ROE, P/E, P/B from the raw numbers using the standard mathematical formulas.
   - Compare with API values from `/api/stock/<sym>` and `/api/stock/<sym>/analysis`. Verify exact or floating-point equivalence.
2. VBP and Real-Time Feed Check:
   - Make 20 repeated calls to `/api/vbp/<sym>` across 5 different symbols.
   - Verify that output is consistent with real OHLC data or returns clean empty array `[]` when no data exists — strictly NO random numbers, NO hardcoded sequences [22.40..22.75].
3. Deliver a clear verdict: **APPROVE** or **REQUEST_CHANGES**.
Record your full report with verification script and outputs in:
`C:\Users\toans\Desktop\Final Market Pulse\market-pulse\.agents\teamwork\teamwork_challenger_2\handoff.md`
When done, message parent orchestrator.
