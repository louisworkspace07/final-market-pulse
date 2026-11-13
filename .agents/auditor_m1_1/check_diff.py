import re
import sys
import difflib

sys.stdout.reconfigure(encoding='utf-8')

DOC_PATH = r'docs/assignment/PRESENTATION_SCRIPT_5W1H_SERVICE.md'
with open(DOC_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

pattern = r'### 2\.[1-6] Diễn Giả [1-6].*?\n#### B\. Lời Thoại Thực Chiến Nguyên Văn \(Full Verbatim Script\)\s*\n\n(>.*?)(?=\n#### C|\n---|\Z)'
matches = re.findall(pattern, content, re.DOTALL)

names = [
    'Speaker 1 (CEO)',
    'Speaker 2 (Product Lead)',
    'Speaker 3 (Marketing Lead)',
    'Speaker 4 (CX Lead)',
    'Speaker 5 (Quality & Risk Lead)',
    'Speaker 6 (PR & Comms Lead)'
]

for i in range(1, 7):
    # From Section 2
    raw = matches[i-1]
    clean_sec2 = re.sub(r'\[.*?\]', '', raw)
    clean_sec2 = re.sub(r'[>*_#]', ' ', clean_sec2)
    words_sec2 = clean_sec2.split()
    text_sec2 = " ".join(words_sec2)
    
    # From Section 6.3
    m = re.search(rf's{i}\s*=\s*"""(.*?)"""', content, re.DOTALL)
    text_s = " ".join(m.group(1).split())
    
    print(f"\n=================== {names[i-1]} ===================")
    print(f"Sec 2 words: {len(words_sec2)} | Sec 6.3 words: {len(text_s.split())}")
    if text_sec2 == text_s:
        print("EXACT MATCH between Section 2 and Section 6.3!")
    else:
        print("DIFFERENCE detected:")
        diff = list(difflib.ndiff(text_sec2.split(), text_s.split()))
        diff_lines = [d for d in diff if d.startswith('+ ') or d.startswith('- ')]
        for d in diff_lines:
            print(f"  {d}")
