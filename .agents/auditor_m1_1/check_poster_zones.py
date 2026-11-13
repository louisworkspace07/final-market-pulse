import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

POSTER_PATH = r'docs/assignment/A0_POSTER_SKETCH_GUIDE.md'
with open(POSTER_PATH, 'r', encoding='utf-8') as f:
    poster = f.read()

zones = re.findall(r'(?:zone\s*[0-6]|central core hub|footer banner).*', poster, re.IGNORECASE)
print(f"Found {len(zones)} zone references in A0_POSTER_SKETCH_GUIDE.md:")
for z in set(zones[:15]):
    print(" ", z.strip())
