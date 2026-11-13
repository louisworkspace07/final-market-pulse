import sys, re
sys.stdout.reconfigure(encoding='utf-8')

with open(r'docs/assignment/PRESENTATION_SCRIPT_5W1H_SERVICE.md', 'r', encoding='utf-8') as f:
    text = f.read()

# Let's inspect all sections
print(f'Total file lines: {len(text.splitlines())}')
print(f'Total characters: {len(text)}')

# Check forbidden terms across the verbatim speech parts
sec2_blocks = re.findall(r'#### B\. Lời Thoại Thực Chiến Nguyên Văn \(Full Verbatim Script\)\s*\n\n(>.*?)(?=\n#### C|\n---|\Z)', text, re.DOTALL)

banned_jargon = [
    'sqlite', 'wal', 'qaoa', 'pennylane', 'piotroski', 'altman', 
    'microservice', 'backend', 'rag', 'api', 'gateway', 'qubit', 
    'hamiltonian', 'pauli', 'python', 'hotfix', 'bn-06', 'bn-07', 
    'sarimax', 'tokenizer', 'json', 'rest api', 'sql', 'crawler',
    'full scan', 'locking', 'thread', 'multiprocessing', 'docker'
]

print('=== SCANNING VERBATIM SCRIPTS FOR TECHNICAL JARGON ===')
for idx, b in enumerate(sec2_blocks):
    clean = re.sub(r'\[.*?\]', '', b).lower()
    found = [j for j in banned_jargon if j in clean]
    print(f'Speaker {idx+1}: {len(found)} banned terms found ({found})')

# Check Cue Cards
cue_cards = re.findall(r'\[CUE CARD [1-6]\].*?(?=\n└|\Z)', text, re.DOTALL)
print(f'\n=== SCANNING CUE CARDS (Found {len(cue_cards)}) ===')
for idx, cc in enumerate(cue_cards):
    found = [j for j in banned_jargon if j in cc.lower()]
    print(f'Cue Card {idx+1}: {len(found)} banned terms found ({found})')

# Check Verbal Transitions
transitions = re.findall(r'\|\s*\*\*Cầu [1-5]\*\*.*?\n', text)
print(f'\n=== SCANNING VERBAL TRANSITION TABLE (Found {len(transitions)} rows) ===')
for t in transitions:
    found = [j for j in banned_jargon if j in t.lower()]
    print(f'Row: {t[:30]}... | Banned terms: {found}')

