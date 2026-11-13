import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

REPORT_PATH = r'docs/assignment/MARKET_PULSE_GLOBAL_REPORT_VI.md'
with open(REPORT_PATH, 'r', encoding='utf-8') as f:
    rep = f.read()

# Search for presentation section in the report
m = re.findall(r'#.*?(?:thuyết trình|presentation|phân vai|diễn giả).*', rep, re.IGNORECASE)
print("Matching section headers in MARKET_PULSE_GLOBAL_REPORT_VI.md:")
for header in m:
    print(" -", header)

# Find where "KỊCH BẢN" or "Diễn giả" appears
lines = rep.splitlines()
matching_lines = [f"Line {idx+1}: {line}" for idx, line in enumerate(lines) if any(k in line.lower() for k in ['diễn giả 1', 'speaker 1', 'phân vai thuyết trình'])]
print(f"\nFound {len(matching_lines)} references:")
for ml in matching_lines[:10]:
    print(" ", ml)
