import sys, re
sys.stdout.reconfigure(encoding='utf-8')

with open('docs/assignment/PRESENTATION_SCRIPT_5W1H_SERVICE.md', 'r', encoding='utf-8') as f:
    text = f.read()

s1 = re.search(r's1 = """(.*?)"""', text, re.DOTALL).group(1)
s2 = re.search(r's2 = """(.*?)"""', text, re.DOTALL).group(1)
s3 = re.search(r's3 = """(.*?)"""', text, re.DOTALL).group(1)
s4 = re.search(r's4 = """(.*?)"""', text, re.DOTALL).group(1)
s5 = re.search(r's5 = """(.*?)"""', text, re.DOTALL).group(1)
s6 = re.search(r's6 = """(.*?)"""', text, re.DOTALL).group(1)

scripts = [
    ('Speaker 1 (CEO)', s1),
    ('Speaker 2 (Product Lead)', s2),
    ('Speaker 3 (Marketing Lead)', s3),
    ('Speaker 4 (CX Lead)', s4),
    ('Speaker 5 (Quality & Risk Lead)', s5),
    ('Speaker 6 (PR & Comms Lead)', s6)
]

print("="*100)
print("PHONETIC & BREATH-GROUP PHRASING ANALYSIS ACROSS ALL 6 SPEAKERS")
print("="*100)

for name, s in scripts:
    words = s.split()
    wc = len(words)
    sentences = [sent.strip() for sent in re.split(r'[\.\?\!](?:\s+|$)', s) if sent.strip()]
    num_sentences = len(sentences)
    commas = s.count(',')
    colons = s.count(':') + s.count(';')
    emdashes = s.count('—')
    
    print(f"\n>>> {name}: {wc} words, {num_sentences} sentences, {commas} commas, {emdashes} em-dashes")
    avg_words_per_sentence = wc / num_sentences
    print(f"    Average sentence length: {avg_words_per_sentence:.1f} words")
    for idx, sent in enumerate(sentences):
        sent_words = len(sent.split())
        sent_commas = sent.count(',')
        print(f"    [{idx+1:02d}] ({sent_words:2d}w, {sent_commas}c): {sent}")
