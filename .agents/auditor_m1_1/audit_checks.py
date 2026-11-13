import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

DOC_PATH = r'docs/assignment/PRESENTATION_SCRIPT_5W1H_SERVICE.md'
REPORT_PATH = r'docs/assignment/MARKET_PULSE_GLOBAL_REPORT_VI.md'

print("=== 1. FILE EXISTENCE AND SIZE CHECKS ===")
if os.path.exists(DOC_PATH):
    size = os.path.getsize(DOC_PATH)
    print(f"PRESENTATION_SCRIPT_5W1H_SERVICE.md exists. Size: {size} bytes")
else:
    print("ERROR: File does not exist!")
    sys.exit(1)

with open(DOC_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.splitlines()
print(f"Total lines: {len(lines)}")

print("\n=== 2. EXTRACT VERBATIM SPEECHES FROM SECTION 2 ===")
pattern = r'### 2\.[1-6] Diễn Giả [1-6].*?\n#### B\. Lời Thoại Thực Chiến Nguyên Văn \(Full Verbatim Script\)\s*\n\n(>.*?)(?=\n#### C|\n---|\Z)'
matches = re.findall(pattern, content, re.DOTALL)
print(f"Found {len(matches)} verbatim speech blocks.")

names = [
    'Speaker 1 (CEO)',
    'Speaker 2 (Product Lead)',
    'Speaker 3 (Marketing Lead)',
    'Speaker 4 (CX Lead)',
    'Speaker 5 (Quality & Risk Lead)',
    'Speaker 6 (PR & Comms Lead)'
]

reported_sec2 = [270, 275, 267, 269, 261, 272]
reported_worker = [271, 279, 274, 273, 265, 272]

spoken_texts = []

for idx, (name, raw) in enumerate(zip(names, matches)):
    # Remove stage cues [Dừng 1 giây...], blockquotes >, asterisks, etc.
    clean_no_cues = re.sub(r'\[.*?\]', '', raw)
    clean_no_cues = re.sub(r'[>*_#]', ' ', clean_no_cues)
    clean_no_cues = re.sub(r'["\'“”‘’]', ' ', clean_no_cues)
    
    words = [w for w in clean_no_cues.split() if w.strip()]
    spoken_texts.append(" ".join(words))
    wc = len(words)
    
    # Also count including stage cues
    clean_with_cues = re.sub(r'[>*_#\[\]]', ' ', raw)
    words_all = [w for w in clean_with_cues.split() if w.strip()]
    
    print(f"\n--- {name} ---")
    print(f"Actual spoken word count (no stage directions): {wc}")
    print(f"Word count including stage cues: {len(words_all)}")
    print(f"Claimed in Section 2 header/6.1: {reported_sec2[idx]}")
    print(f"Claimed in worker_m1 handoff: {reported_worker[idx]}")
    print(f"Within guardrail [240, 280]: {240 <= wc <= 280}")
    est_seconds_125 = wc / 125 * 60
    est_seconds_135 = wc / 135 * 60
    print(f"Estimated speech duration (125-135 wpm): {est_seconds_135:.1f}s - {est_seconds_125:.1f}s (~{wc/130*60:.1f}s at 130 wpm)")

print("\n=== 3. SECTION 6.3 PYTHON CODE TEXT COMPARISON ===")
# Let's extract s1..s6 from the python script in Section 6.3
s_vars = {}
for i in range(1, 7):
    m = re.search(rf's{i}\s*=\s*"""(.*?)"""', content, re.DOTALL)
    if m:
        s_text = m.group(1)
        s_words = [w for w in s_text.split() if w.strip()]
        s_vars[f's{i}'] = len(s_words)
        print(f"Section 6.3 s{i} word count: {len(s_words)}")
    else:
        print(f"Section 6.3 s{i} NOT found!")

print("\n=== 4. BANNED JARGON SCAN ACROSS ENTIRE SPOKEN TEXT ===")
banned_jargon = [
    'sqlite', 'wal', 'qaoa', 'pennylane', 'piotroski', 'altman', 
    'microservice', 'backend', 'rag', 'api', 'gateway', 'qubit', 
    'hamiltonian', 'pauli', 'python', 'hotfix', 'bn-06', 'bn-07', 
    'sarimax', 'tokenizer', 'json'
]

total_jargon_found = 0
for idx, (name, sp_text) in enumerate(zip(names, spoken_texts)):
    text_lower = sp_text.lower()
    for bj in banned_jargon:
        if bj in text_lower:
            print(f"VIOLATION: {name} contains banned jargon: '{bj}'")
            total_jargon_found += 1

if total_jargon_found == 0:
    print("Zero banned jargon found in all 6 spoken texts! PASS.")

print("\n=== 5. PLAGIARISM / LAZY COPY-PASTE CHECK AGAINST MARKET_PULSE_GLOBAL_REPORT_VI.md ===")
if os.path.exists(REPORT_PATH):
    with open(REPORT_PATH, 'r', encoding='utf-8') as f:
        report_vi = f.read()
    print(f"Loaded MARKET_PULSE_GLOBAL_REPORT_VI.md ({len(report_vi)} chars).")
    
    # Check n-gram overlap or long verbatim sentences from report_vi in presentation script
    # Let's check sentences of >= 8 consecutive words
    import unicodedata
    def normalize_text(t):
        t = unicodedata.normalize('NFC', t.lower())
        t = re.sub(r'[^\w\s]', ' ', t)
        return " ".join(t.split())
    
    norm_report = normalize_text(report_vi)
    
    total_long_matches = 0
    for idx, (name, sp_text) in enumerate(zip(names, spoken_texts)):
        norm_spoken = normalize_text(sp_text)
        spoken_words = norm_spoken.split()
        
        # Check 8-grams
        ngram_size = 8
        found_ngrams = []
        for i in range(len(spoken_words) - ngram_size + 1):
            ngram = " ".join(spoken_words[i:i+ngram_size])
            if ngram in norm_report:
                found_ngrams.append(ngram)
        
        print(f"{name}: {len(found_ngrams)} 8-word overlaps with technical report.")
        if found_ngrams:
            for ng in found_ngrams[:3]:
                print(f"   Example overlap: '{ng}'")
else:
    print("MARKET_PULSE_GLOBAL_REPORT_VI.md not found!")

print("\n=== 6. FACADE & STUB CHECK ===")
# Check for stubs, 'TBD', 'TODO', 'lorem ipsum', empty sections
stubs = re.findall(r'(todo|tbd|placeholder|lorem ipsum|coming soon|cần bổ sung)', content, re.IGNORECASE)
print(f"Stubs/placeholders found: {len(stubs)} -> {stubs}")
