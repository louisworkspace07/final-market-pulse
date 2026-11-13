import sys, re, difflib

sys.stdout.reconfigure(encoding='utf-8')

filepath = r'docs/assignment/PRESENTATION_SCRIPT_5W1H_SERVICE.md'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

pattern = r'### 2\.[1-6] Diễn Giả [1-6].*?\n#### B\. Lời Thoại Thực Chiến Nguyên Văn \(Full Verbatim Script\)\s*\n\n(>.*?)(?=\n#### C|\n---|\Z)'
matches = re.findall(pattern, content, re.DOTALL)

loc = {}
code_match = re.search(r'`python\n(.*?)`', content[content.find('### 6.3'):], re.DOTALL)
exec(code_match.group(1), {}, loc)

names = ['Speaker 1', 'Speaker 2', 'Speaker 3', 'Speaker 4', 'Speaker 5', 'Speaker 6']

for idx, (raw_sec2, s_code) in enumerate(zip(matches, loc['scripts'])):
    clean_sec2 = re.sub(r'\[.*?\]', '', raw_sec2).replace('>', ' ').replace('*', ' ').replace('\'', ' ')
    w_sec2 = [w.strip() for w in clean_sec2.split() if w.strip()]
    w_code = [w.strip() for w in s_code.replace('\'', ' ').split() if w.strip()]
    print(f'=== {names[idx]} ===')
    print(f'Section 2 word count: {len(w_sec2)} vs Code string word count: {len(w_code)}')
    # Let\'s find differences
    diff = list(difflib.unified_diff(w_code, w_sec2, lineterm=''))
    if diff:
        print('Diff (Code -> Sec2):')
        for d in diff[:10]:
            print('  ', d)
