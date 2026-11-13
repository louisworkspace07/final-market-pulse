import sys, re
sys.stdout.reconfigure(encoding='utf-8')

with open(r'docs/assignment/PRESENTATION_SCRIPT_5W1H_SERVICE.md', 'r', encoding='utf-8') as f:
    text = f.read()

sec2_blocks = re.findall(r'#### B\. Lời Thoại Thực Chiến Nguyên Văn \(Full Verbatim Script\)\s*\n\n(>.*?)(?=\n#### C|\n---|\Z)', text, re.DOTALL)

# Extract table rows in Section IV
rows = re.findall(r'\|\s*\*\*Cầu [1-5]\*\*.*?\n', text)

print('=== CHECKING VERBAL TRANSITION CONSISTENCY ===')
for idx, r in enumerate(rows):
    cols = [c.strip() for c in r.split('|')[1:-1]]
    bridge_num = cols[0]
    speakers = cols[1]
    outgoing = cols[2].replace('*', '').replace('"', '').strip()
    incoming = cols[3].replace('*', '').replace('"', '').strip()
    # Check against sec2_blocks[idx] end and sec2_blocks[idx+1] start
    s_curr = re.sub(r'\[.*?\]', '', sec2_blocks[idx]).replace('>', ' ').replace('*', ' ').replace('"', ' ').strip()
    s_next = re.sub(r'\[.*?\]', '', sec2_blocks[idx+1]).replace('>', ' ').replace('*', ' ').replace('"', ' ').strip()
    
    # check outgoing in s_curr
    out_found = outgoing[:30] in s_curr
    # check incoming in s_next
    inc_found = incoming[:30] in s_next
    print(f'{bridge_num}: {speakers}')
    print(f'  Outgoing matches Sec2: {out_found} ("{outgoing[:40]}...")')
    print(f'  Incoming matches Sec2: {inc_found} ("{incoming[:40]}...")')

