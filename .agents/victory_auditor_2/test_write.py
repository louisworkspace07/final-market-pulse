import sys, re, os, datetime

sys.stdout.reconfigure(encoding='utf-8')

print('=' * 70)
print('VICTORY AUDIT INDEPENDENT VERIFICATION SUITE')
print('=' * 70)

target_file = 'docs/assignment/PRESENTATION_SCRIPT_5W1H_SERVICE.md'
if not os.path.exists(target_file):
    print(f'CRITICAL FAIL: Target file does not exist: {target_file}')
    sys.exit(1)

with open(target_file, 'r', encoding='utf-8') as f:
    full_text = f.read()

lines = full_text.splitlines()
print(f'Target deliverable: {target_file}')
print(f'File size: {len(full_text.encode("utf-8"))} bytes | {len(lines)} lines | {len(full_text)} characters')

# Check file stats
st = os.stat(target_file)
ctime = datetime.datetime.fromtimestamp(st.st_ctime).isoformat()
mtime = datetime.datetime.fromtimestamp(st.st_mtime).isoformat()
print(f'Created: {ctime} | Modified: {mtime}')

print('\n' + '-' * 70)
print('CHECK 1: PLACEHOLDER & FACADE SCAN')
print('-' * 70)

placeholders = ['TODO', 'FIXME', 'TBD', 'XXX', 'LOREM IPSUM', '[CHÈN', '[BỔ SUNG', '<CHÈN', 'PLACEHOLDER']
found_placeholders = []
for p in placeholders:
    m = re.findall(re.escape(p), full_text, re.IGNORECASE)
    if m:
        found_placeholders.append((p, len(m)))

if found_placeholders:
    print(f'FAIL: Found placeholders: {found_placeholders}')
else:
    print('PASS: Zero placeholder / facade tokens detected across entire document.')

print('\n' + '-' * 70)
print('CHECK 2: 5W1H STRUCTURE & 6-SPEAKER MAPPING & WORD COUNTS')
print('-' * 70)

speakers = [
    ('Speaker 1', 'CEO', 'WHO', '2.1 Diễn Giả 1 — CEO'),
    ('Speaker 2', 'Product Lead', 'WHAT', '2.2 Diễn Giả 2 — Product Lead'),
    ('Speaker 3', 'Marketing Lead', 'WHEN & WHERE', '2.3 Diễn Giả 3 — Marketing Lead'),
    ('Speaker 4', 'CX Lead', 'HOW', '2.4 Diễn Giả 4 — CX Lead'),
    ('Speaker 5', 'Quality & Risk Lead', 'WHY', '2.5 Diễn Giả 5 — Quality & Risk Lead'),
    ('Speaker 6', 'PR & Comms Lead', 'VISION & CLOSING', '2.6 Diễn Giả 6 — PR & Comms Lead')
]

speaker_data = []
all_matched = True

for sp_id, role, dimension, section_header in speakers:
    pat = rf'### {re.escape(section_header)}.*?#### B\. Lời Thoại Thực Chiến Nguyên Văn.*?\n(.*?)(?=#### C|\Z)'
    m = re.search(pat, full_text, re.DOTALL)
    if not m:
        print(f'FAIL: Section not found for {sp_id} ({role}) - {section_header}')
        all_matched = False
        continue
    
    raw_block = m.group(1).strip()
    # Strip blockquotes >
    clean_lines = [l.strip().lstrip('>').strip() for l in raw_block.splitlines() if l.strip()]
    raw_speech = ' '.join(clean_lines)
    
    # Strip bracketed cues
    spoken_only = re.sub(r'(\*?\*?\[.*?\]\*?\*?)|(\*?\*?\(.*?\)\*?\*?)', ' ', raw_speech)
    
    # Spoken tokens
    raw_tokens = spoken_only.split()
    clean_tokens = []
    for t in raw_tokens:
        tok = t.strip('\"\'“”«».,;:!?–—()[]{}*')
        if tok and tok not in ['-', '–', '—']:
            clean_tokens.append(tok)
            
    word_count = len(clean_tokens)
    
    # Claimed word count in Section A
    pat_claimed = rf'### {re.escape(section_header)}.*?#### A\. Bảng Thông Số Kỹ Thuật.*?Số từ thoại chính xác.*?\*\*(\d+)\s*từ\*\*'
    m_cl = re.search(pat_claimed, full_text, re.DOTALL)
    claimed_cnt = int(m_cl.group(1)) if m_cl else None
    
    # Verify range 240-280
    in_range = (240 <= word_count <= 280)
    
    # Estimated speaking duration at 130 WPM and 138 WPM
    dur_130 = word_count / (130 / 60)
    dur_138 = word_count / (138 / 60)
    
    speaker_data.append({
        'sp_id': sp_id,
        'role': role,
        'dimension': dimension,
        'section_header': section_header,
        'spoken_text': ' '.join(clean_tokens),
        'word_count': word_count,
        'claimed_count': claimed_cnt,
        'in_range': in_range,
        'duration_130': dur_130,
        'duration_138': dur_138
    })
    
    status_str = 'PASS' if in_range else 'FAIL'
    match_claim = 'MATCH' if (word_count == claimed_cnt) else f'DIFF({word_count - (claimed_cnt or 0)})'
    print(f'{sp_id:9} | {role:20} | 5W1H: {dimension:16} | Count: {word_count:3d} | Claimed: {claimed_cnt} [{match_claim}] | Range [240-280]: {status_str}')

total_spoken_words = sum(s['word_count'] for s in speaker_data)
print(f'TOTAL SPOKEN WORDS ACROSS 6 SPEAKERS: {total_spoken_words}')
total_time_130 = sum(s['duration_130'] for s in speaker_data)
total_time_138 = sum(s['duration_138'] for s in speaker_data)
print(f'Total speaking time at 130 WPM: {total_time_130:.1f}s ({total_time_130/60:.2f} min)')
print(f'Total speaking time at 138 WPM: {total_time_138:.1f}s ({total_time_138/60:.2f} min)')

print('\n' + '-' * 70)
print('CHECK 3: PROHIBITED BACKEND & TECHNICAL JARGON IN SPOKEN SCRIPTS')
print('-' * 70)

forbidden_terms = [
    (r'\bsqlite\b', 'sqlite'),
    (r'\bwal\b', 'wal'),
    (r'\bapi\b', 'api'),
    (r'\brest\b', 'rest'),
    (r'\bgateway\b', 'gateway'),
    (r'\bcrawler\b', 'crawler'),
    (r'\bcrawl\b', 'crawl'),
    (r'\bscraping\b', 'scraping'),
    (r'\bpython\b', 'python'),
    (r'\bjavascript\b', 'javascript'),
    (r'\bflask\b', 'flask'),
    (r'\bpandas\b', 'pandas'),
    (r'\bdataframe\b', 'dataframe'),
    (r'\bnumpy\b', 'numpy'),
    (r'\bqaoa\b', 'qaoa'),
    (r'\bqubo\b', 'qubo'),
    (r'\bpennylane\b', 'pennylane'),
    (r'\baltman\b', 'altman'),
    (r'\bpiotroski\b', 'piotroski'),
    (r'\bz-score\b', 'z-score'),
    (r'\bf-score\b', 'f-score'),
    (r'\bbackend\b', 'backend'),
    (r'\bfrontend\b', 'frontend'),
    (r'\bmicroservice\b', 'microservice'),
    (r'\bmicroservices\b', 'microservices'),
    (r'\bserverless\b', 'serverless'),
    (r'\bdocker\b', 'docker'),
    (r'\bkubernetes\b', 'kubernetes'),
    (r'\bredis\b', 'redis'),
    (r'\bn\+1\b', 'n+1'),
    (r'\bcpu\b', 'cpu'),
    (r'\bconcurrency\b', 'concurrency'),
    (r'\basync\b', 'async'),
    (r'\bawait\b', 'await'),
    (r'\bendpoint\b', 'endpoint'),
    (r'\bhttp\b', 'http'),
    (r'\bjson\b', 'json'),
    (r'\bschema\b', 'schema'),
    (r'\bdatabase\b', 'database'),
    (r'\bcsdl\b', 'csdl'),
    (r'\bcơ sở dữ liệu\b', 'cơ sở dữ liệu'),
    (r'\btruy vấn\b', 'truy vấn'),
    (r'\bthuật toán\b', 'thuật toán')
]

jargon_violations = []
for s in speaker_data:
    sp_id = s['sp_id']
    text = s['spoken_text']
    for pat, label in forbidden_terms:
        matches = re.findall(pat, text, re.IGNORECASE)
        if matches:
            jargon_violations.append((sp_id, label, matches))

if jargon_violations:
    print(f'FAIL: Found {len(jargon_violations)} jargon violations in spoken text:')
    for j in jargon_violations:
        print(f'   - {j[0]}: {j[1]} -> {j[2]}')
else:
    print('PASS: ZERO prohibited backend/technical jargon found in any spoken verbatim script!')

print('\n' + '-' * 70)
print('CHECK 4: CUE CARDS / FLASHCARDS VERIFICATION')
print('-' * 70)

cue_cards_pat = r'## PHẦN III: HỆ THỐNG THẺ GHI NHỚ CẦM TAY TOÀN ĐỘI.*?(?=## PHẦN IV|\Z)'
m_cue = re.search(cue_cards_pat, full_text, re.DOTALL)
if not m_cue:
    print('FAIL: PHẦN III (Hệ thống thẻ ghi nhớ) not found')
else:
    cue_text = m_cue.group(0)
    card_blocks = re.findall(r'(\[CUE CARD \d+\].*?└─+┘)', cue_text, re.DOTALL)
    print(f'Found {len(card_blocks)} master cue cards in Phần III.')
    for idx, card in enumerate(card_blocks, 1):
        first_line = card.splitlines()[0].strip()
        bullets = re.findall(r'•\s+BULLET\s+\d+', card)
        has_hook = 'OPENING CUE' in card or 'INCOMING HOOK' in card
        has_poster = 'ĐIỂM NEO POSTER' in card
        has_outgoing = 'CÂU BÀN GIAO' in card or 'LỜI TUYÊN BỐ KẾT THÚC' in card
        status = 'PASS' if len(bullets) in [3, 4] and has_hook and has_poster and has_outgoing else 'FAIL'
        print(f'{first_line:65} | Bullets: {len(bullets)} | Hook: {has_hook} | Poster: {has_poster} | Outgoing: {has_outgoing} | {status}')

print('\n' + '-' * 70)
print('CHECK 5: VERBAL TRANSITIONS VERIFICATION')
print('-' * 70)

trans_pat = r'## PHẦN IV: ĐỘNG CƠ CHUYỂN TIẾP LỜI THOẠI TOÀN DIỆN.*?(?=## PHẦN V|\Z)'
m_trans = re.search(trans_pat, full_text, re.DOTALL)
if not m_trans:
    print('FAIL: PHẦN IV (Động cơ chuyển tiếp) not found')
else:
    trans_text = m_trans.group(0)
    bridges = re.findall(r'\|\s+\*\*Cầu\s+(\d+)\*\*\s+\|\s+\*\*(.*?)\*\*\s+\|\s+\*(.*?)\*\s+\|\s+\*(.*?)\*\s+\|\s+(.*?)\s+\|', trans_text)
    print(f'Found {len(bridges)} explicit verbal bridge rows in Phần IV table:')
    for b_num, pair, out_lead, inc_hook, logic in bridges:
        print(f'   - Bridge {b_num}: {pair}')
        print(f'     Outgoing: {out_lead[:70]}...')
        print(f'     Incoming: {inc_hook[:70]}...')
        print(f'     Logic   : {logic[:70]}...')

print('\n' + '-' * 70)
print('CHECK 6: STAGE CHOREOGRAPHY & BODY LANGUAGE VERIFICATION')
print('-' * 70)

stage_pat = r'## PHẦN V: NGHỆ THUẬT ĐIỀU PHỐI SÂN KHẤU.*?(?=## PHẦN VI|\Z)'
m_stage = re.search(stage_pat, full_text, re.DOTALL)
if not m_stage:
    print('FAIL: PHẦN V (Nghệ thuật điều phối sân khấu) not found')
else:
    st_text = m_stage.group(0)
    has_geometry = 'Sơ Đồ Hình Học Sân Khấu Bất Đối Xứng' in st_text or 'Asymmetric Open Crescent' in st_text
    has_easel = '35°' in st_text
    has_gaze = '60-30-10' in st_text
    has_touch = 'Touch, Turn, Talk' in st_text
    has_bow = 'Cúi Chào Đồng Bộ' in st_text or '15°' in st_text
    has_table = 'Bảng Tọa Độ Không Gian & Tầm Nhìn Sân Khấu' in st_text
    print(f'Stage features:')
    print(f'   - Asymmetric Crescent Geometry: {has_geometry}')
    print(f'   - 35° Angled Easel: {has_easel}')
    print(f'   - Coordinate Table (X, Y, Angle, Sightline): {has_table}')
    print(f'   - 60-30-10 Gaze Rule: {has_gaze}')
    print(f'   - Touch, Turn, Talk Rule: {has_touch}')
    print(f'   - 5-Phase Synchronized 15° Bow: {has_bow}')

print('\n' + '-' * 70)
print('CHECK 7: LEGAL COMPLIANCE & ACCEPTANCE CRITERIA AUDIT')
print('-' * 70)

# Check compliance with Article 71 Securities Law 2019
has_art71 = 'Điều 71 Luật Chứng khoán' in full_text or 'Điều 71' in full_text
# Check Decree 13/2023/ND-CP on Personal Data Protection
has_dec13 = 'Nghị định 13' in full_text
# Check no illegal stock pumping
no_pump = 'không \"phím hàng\"' in full_text.lower() or 'không phím hàng' in full_text.lower()
# Check student package
has_student = '0 đồng' in full_text or 'miễn phí' in full_text

print(f'Legal & Policy Compliance:')
print(f'   - Article 71 Securities Law 2019: {has_art71}')
print(f'   - Decree 13/2023/ND-CP Data Protection: {has_dec13}')
print(f'   - Anti-pumping / Ethical Commitment: {no_pump}')
print(f'   - Student Experience Package / 0 VND: {has_student}')

print('\n' + '=' * 70)
print('INDEPENDENT VERIFICATION COMPLETE')
print('=' * 70)
