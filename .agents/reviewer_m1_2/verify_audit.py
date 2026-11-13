import re
import sys
import difflib

sys.stdout.reconfigure(encoding='utf-8')

filepath = r'docs/assignment/PRESENTATION_SCRIPT_5W1H_SERVICE.md'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

pattern = r'### 2\.[1-6] Diễn Giả ([1-6]).*?\n#### B\. Lời Thoại Thực Chiến Nguyên Văn \(Full Verbatim Script\)\s*\n\n(>.*?)(?=\n#### C|\n---|\Z)'
matches = re.findall(pattern, content, re.DOTALL)

s_pattern = r's([1-6]) = """(.*?)"""'
s_matches = re.findall(s_pattern, content, re.DOTALL)

print("=== 1. VERIFY EXACT TEXT MATCH (SEC II vs SEC 6.3) ===")
for idx in range(6):
    num, script = matches[idx]
    s_num, s_text = s_matches[idx]
    
    clean_sec2 = re.sub(r'\[.*?\]', '', script)
    clean_sec2 = clean_sec2.replace('>', ' ').replace('*', '').replace('"', '').replace("'", '').strip()
    clean_sec2 = ' '.join(clean_sec2.split())
    
    clean_s = s_text.replace('"', '').replace("'", '').strip()
    clean_s = ' '.join(clean_s.split())
    
    if clean_sec2 == clean_s:
        print(f'Speaker {num}: 100% PERFECT TEXT MATCH')
    else:
        print(f'Speaker {num}: Text difference found!')
        diff = list(difflib.ndiff(clean_sec2.split(), clean_s.split()))
        diff_lines = [d for d in diff if d.startswith('+') or d.startswith('-')]
        print('  Diff:', diff_lines)

print("\n=== 2. VERIFY WORD COUNTS UNDER MULTIPLE TOKENIZERS ===")
speaker_roles = [
    "Speaker 1 (CEO)",
    "Speaker 2 (Product Lead)",
    "Speaker 3 (Marketing Lead)",
    "Speaker 4 (CX Lead)",
    "Speaker 5 (Quality & Risk Lead)",
    "Speaker 6 (PR & Comms Lead)"
]

for idx in range(6):
    num, script = matches[idx]
    clean_sec2 = re.sub(r'\[.*?\]', '', script)
    
    # Method A: naive split after stripping * and >
    clean_a = clean_sec2.replace('>', ' ').replace('*', ' ').replace("'", ' ').replace('"', ' ')
    tokens_a = [w for w in clean_a.split() if w.strip()]
    
    # Method B: proper word tokens (filtering isolated punctuation)
    tokens_b = [w for w in tokens_a if any(c.isalnum() for c in w)]
    
    # Method C: regex word tokens
    tokens_c = re.findall(r'\b[\w\d–-]+\b', clean_sec2, re.UNICODE)
    tokens_c = [w for w in tokens_c if any(c.isalnum() for c in w)]
    
    # Method D: Section 6.3 s strings split
    s_tokens = s_matches[idx][1].split()
    
    print(f"{speaker_roles[idx]}:")
    print(f"  Method A (naive split with punct tokens): {len(tokens_a)} words")
    print(f"  Method B (filtered alnum tokens):         {len(tokens_b)} words")
    print(f"  Method C (regex word tokens):             {len(tokens_c)} words")
    print(f"  Method D (Section 6.3 s_strings):         {len(s_tokens)} words")
    print(f"  All methods within [240, 280]? -> {all(240 <= c <= 280 for c in [len(tokens_a), len(tokens_b), len(tokens_c), len(s_tokens)])}")

print("\n=== 3. CHECK EXTENSIVE BANNED BACKEND JARGON ===")
extended_banned_jargon = [
    'sqlite', 'wal', 'qaoa', 'pennylane', 'piotroski', 'altman', 
    'microservice', 'backend', 'rag', 'api', 'gateway', 'qubit', 
    'hamiltonian', 'pauli', 'python', 'hotfix', 'bn-06', 'bn-07', 
    'sarimax', 'tokenizer', 'json', 'sql', 'database', 'docker',
    'kubernetes', 'redis', 'kafka', 'celery', 'nosql', 'postgres',
    'orm', 'http', 'restful', 'graphql', 'endpoint', 'frontend',
    'full scan', 'cpu throttling', 'latency', 'cache hit', 'ttl'
]

for idx in range(6):
    num, script = matches[idx]
    clean_sec2 = re.sub(r'\[.*?\]', '', script).lower()
    found_jargon = []
    for j in extended_banned_jargon:
        # Check whole word match or substring
        if re.search(r'\b' + re.escape(j) + r'\b', clean_sec2):
            found_jargon.append(j)
    if found_jargon:
        print(f"FAILED: {speaker_roles[idx]} contains jargon: {found_jargon}")
    else:
        print(f"PASSED: {speaker_roles[idx]} ZERO backend jargon detected")

print("\n=== 4. CHECK MANDATORY UTILITIES IN SPEAKER 2 ===")
s2_text = matches[1][1]
req_utilities = [
    ("Điểm sức khỏe", "Điểm sức khỏe tài chính 0–100"),
    ("Đèn Giao Thông", "Radar cảnh báo rủi ro Đèn Giao Thông"),
    ("Trợ lý hỏi đáp", "Trợ lý hỏi đáp trích dẫn nguồn minh bạch"),
    ("Bảng so sánh", "Bảng so sánh vị thế cùng ngành")
]
for short_name, full_name in req_utilities:
    found = short_name.lower() in s2_text.lower()
    print(f"  Utility '{full_name}': {'FOUND' if found else 'MISSING'}")

print("\n=== 5. CHECK LEGAL COMPLIANCE IN SPEAKER 5 ===")
s5_text = matches[4][1]
legal_checks = [
    ("Điều 71 Luật Chứng khoán", "Điều 71 Luật Chứng khoán 2019"),
    ("Nghị định 13", "Nghị định 13/2023/NĐ-CP (Bảo mật dữ liệu cá nhân)"),
    ("phím hàng", "Kiên quyết nói KHÔNG với 'phím hàng'"),
    ("hoa hồng", "0% hoa hồng môi giới (tính khách quan, độc lập)"),
    ("lợi nhuận", "Không cam kết/hứa hẹn lợi nhuận viển vông")
]
for term, desc in legal_checks:
    found = term.lower() in s5_text.lower()
    print(f"  Legal item '{desc}': {'FOUND' if found else 'MISSING'}")

print("\n=== 6. CHECK STAGE DIRECTIONS AND TRANSITIONS ===")
for idx in range(6):
    num, script = matches[idx]
    cues = re.findall(r'\[(.*?)\]', script)
    print(f"{speaker_roles[idx]}: {len(cues)} inline stage direction cues found -> {cues}")

print("\nAudit completed.")
