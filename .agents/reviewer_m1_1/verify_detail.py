import sys, re, difflib
sys.stdout.reconfigure(encoding='utf-8')

with open(r'docs/assignment/PRESENTATION_SCRIPT_5W1H_SERVICE.md', 'r', encoding='utf-8') as f:
    text = f.read()

sec2_blocks = re.findall(r'#### B\. Lời Thoại Thực Chiến Nguyên Văn \(Full Verbatim Script\)\s*\n\n(>.*?)(?=\n#### C|\n---|\Z)', text, re.DOTALL)

sec6_code = re.search(r'### 6\.3 Mã Nguồn Python.*?```python(.*?)```', text, re.DOTALL).group(1)
loc = {}
exec(sec6_code, {}, loc)
code_scripts = loc['scripts']

names = ['Speaker 1 (CEO)', 'Speaker 2 (Product Lead)', 'Speaker 3 (Marketing Lead)', 'Speaker 4 (CX Lead)', 'Speaker 5 (Quality & Risk Lead)', 'Speaker 6 (PR & Comms Lead)']

print('=== COMPARISON: SECTION II VERBATIM vs SECTION 6.3 CODE STRINGS ===')
for i in range(6):
    s_sec2_raw = sec2_blocks[i]
    lines = [re.sub(r'^>\s*', '', l) for l in s_sec2_raw.splitlines()]
    s_sec2_text = ' '.join(lines)
    s_sec2_clean = re.sub(r'\[.*?\]', '', s_sec2_text)
    s_sec2_clean = s_sec2_clean.replace('*', '').replace('"', '').replace("'", "")
    words_sec2 = s_sec2_clean.split()
    
    clean_code = code_scripts[i].replace('*', '').replace('"', '').replace("'", "")
    words_code = clean_code.split()
    
    print(f'\n--- {names[i]} ---')
    print(f'Sec 2 count: {len(words_sec2)} | Code count: {len(words_code)}')
    if words_sec2 == words_code:
        print('Result: EXACT 100% MATCH!')
    else:
        print('Differences detected:')
        diff = [d for d in difflib.ndiff(words_code, words_sec2) if d.startswith('+ ') or d.startswith('- ')]
        for d in diff:
            print(f'  {d}')
