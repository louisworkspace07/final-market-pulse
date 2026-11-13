import re
import sys

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
    raw = matches[i-1]
    # Remove stage cues [Dừng 1 giây...]
    no_cues = re.sub(r'\[.*?\]', '', raw)
    
    # Method A: Just remove markdown '>' and stage cues, keep punctuation attached to words, just strip *
    # If markdown is **word**: or **word**. -> replace ** with empty string!
    clean_no_md = no_cues.replace('>', '').replace('**', '').replace('*', '')
    # Now split on whitespace
    words_method_a = [w for w in clean_no_md.split() if w.strip()]
    
    # Method B: Regex \S+ after removing markdown and cues
    words_method_b = re.findall(r'\S+', clean_no_md)
    
    # Method C: Remove all punctuation, count pure words
    pure_words = re.findall(r'[a-zA-Z0-9àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệđìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵ]+', clean_no_md)
    
    print(f"{names[i-1]}:")
    print(f"  Method A (strip markdown **, then split): {len(words_method_a)} words")
    print(f"  Method C (pure words without punctuation): {len(pure_words)} words")
    
    # Check Section 6.3 variable s{i}
    m = re.search(rf's{i}\s*=\s*"""(.*?)"""', content, re.DOTALL)
    s_words = [w for w in m.group(1).split() if w.strip()]
    print(f"  Section 6.3 s{i} split(): {len(s_words)} words")
    print(f"  All methods within [240, 280]: {240 <= len(words_method_a) <= 280 and 240 <= len(s_words) <= 280}")
