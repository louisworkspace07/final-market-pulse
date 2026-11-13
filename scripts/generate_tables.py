import sys, re
sys.stdout.reconfigure(encoding='utf-8')

with open('docs/assignment/PRESENTATION_SCRIPT_5W1H_SERVICE.md', 'r', encoding='utf-8') as f:
    doc = f.read()

# 1. Cue cards audit
part3 = re.search(r'## PHẦN III:.*?(?=## PHẦN IV:)', doc, re.DOTALL).group(0)
cards = re.findall(r'(\[CUE CARD \d+\].*?)(?=(?:\[CUE CARD \d+\]|```))', part3, re.DOTALL)

print("### 1. CUE CARDS AUDIT TABLE")
print("| Card # | Title | Bullets Count | Compliant (3-4)? | Incoming Hook Present? | Handover Present? | Word Count |")
print("|---|---|---|---|---|---|---|")
for i, c in enumerate(cards, 1):
    title_m = re.search(r'\[CUE CARD \d+\]\s*—\s*(.*?)\s*│', c)
    title = title_m.group(1).strip() if title_m else f"Card {i}"
    bullets = re.findall(r'│\s*•\s*(BULLET\s*\d+.*?)(?=(?:│\s*•|│\s*───|│\s*➔))', c, re.DOTALL)
    incoming = "Xin cảm ơn" in c or "INCOMING" in c
    handover = ("CÂU BÀN GIAO" in c or "LỜI TUYÊN BỐ" in c)
    wc = len(c.split())
    comp = "YES (4 bullets)" if 3 <= len(bullets) <= 4 else f"NO ({len(bullets)})"
    inc_str = "YES" if incoming else "NO (Missing)"
    ho_str = "YES" if handover else "NO"
    print(f"| Card {i} | {title[:35]} | {len(bullets)} | {comp} | {inc_str} | {ho_str} | {wc} |")

# 2. Timing and Pause Simulation Table
s1 = re.search(r's1 = """(.*?)"""', doc, re.DOTALL).group(1)
s2 = re.search(r's2 = """(.*?)"""', doc, re.DOTALL).group(1)
s3 = re.search(r's3 = """(.*?)"""', doc, re.DOTALL).group(1)
s4 = re.search(r's4 = """(.*?)"""', doc, re.DOTALL).group(1)
s5 = re.search(r's5 = """(.*?)"""', doc, re.DOTALL).group(1)
s6 = re.search(r's6 = """(.*?)"""', doc, re.DOTALL).group(1)

speakers = [
    ("Speaker 1 (CEO)", s1),
    ("Speaker 2 (Product Lead)", s2),
    ("Speaker 3 (Marketing Lead)", s3),
    ("Speaker 4 (CX Lead)", s4),
    ("Speaker 5 (Quality & Risk Lead)", s5),
    ("Speaker 6 (PR & Comms Lead)", s6)
]

print("\n### 2. PUNCTUATION & PAUSE ANALYSIS TABLE")
print("| Speaker | Words | Commas (0.5s) | Sentence Ends (1.0s) | Em-dashes (1.5s) | Total Pause Time | Claimed Time (Doc) |")
print("|---|---|---|---|---|---|---|")
for name, s in speakers:
    wc = len(s.split())
    c_cnt = s.count(',')
    p_cnt = len(re.findall(r'[\.\?\!](?:\s|$)', s))
    e_cnt = s.count('—')
    pause = (c_cnt * 0.5) + (p_cnt * 1.0) + (e_cnt * 1.5)
    # Claimed time from doc table
    claimed_m = re.search(re.escape(name.split()[0] + " " + name.split()[1]) + r'.*?(\d+\s*giây)', doc)
    claimed = claimed_m.group(1) if claimed_m else "~120s"
    print(f"| {name} | {wc} | {c_cnt} ({c_cnt*0.5:.1f}s) | {p_cnt} ({p_cnt*1.0:.1f}s) | {e_cnt} ({e_cnt*1.5:.1f}s) | **{pause:.1f}s** | {claimed} |")

print("\n### 3. DELIVERY TIME AT VARIOUS CADENCES TABLE (Threshold: 100s - 120s)")
print("| Speaker | @ 120 WPM | @ 125 WPM | @ 130 WPM (Author claim) | @ 140 WPM | Max Safe WPM for 120s | Overrun @ 130 WPM | Status |")
print("|---|---|---|---|---|---|---|---|")
for name, s in speakers:
    wc = len(s.split())
    c_cnt = s.count(',')
    p_cnt = len(re.findall(r'[\.\?\!](?:\s|$)', s))
    e_cnt = s.count('—')
    pause = (c_cnt * 0.5) + (p_cnt * 1.0) + (e_cnt * 1.5)
    
    t120 = (wc/120)*60 + pause
    t125 = (wc/125)*60 + pause
    t130 = (wc/130)*60 + pause
    t140 = (wc/140)*60 + pause
    
    # Required WPM to hit 120s
    req_wpm = (wc / (120 - pause)) * 60
    over130 = t130 - 120
    status = "**FAIL (>120s)**" if t130 > 120 else "PASS"
    print(f"| {name} | {t120:.1f}s | {t125:.1f}s | {t130:.1f}s | {t140:.1f}s | **{req_wpm:.1f} WPM** | +{over130:.1f}s | {status} |")
