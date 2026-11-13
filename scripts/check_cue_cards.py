import sys, re
sys.stdout.reconfigure(encoding='utf-8')

with open('docs/assignment/PRESENTATION_SCRIPT_5W1H_SERVICE.md', 'r', encoding='utf-8') as f:
    text = f.read()

part3_match = re.search(r'## PHẦN III:.*?(?=## PHẦN IV:)', text, re.DOTALL)
part3 = part3_match.group(0)

cards = re.findall(r'(\[CUE CARD \d+\].*?)(?=(?:\[CUE CARD \d+\]|```))', part3, re.DOTALL)

print(f"Total Cue Cards found: {len(cards)}")

for i, card in enumerate(cards, 1):
    header = card.strip().split('\n')[0]
    bullets = re.findall(r'│\s*•\s*(BULLET\s*\d+.*?)(?=(?:│\s*•|│\s*───|│\s*➔))', card, re.DOTALL)
    neo = re.findall(r'│\s*•\s*ĐIỂM NEO.*', card)
    handover = re.findall(r'│\s*➔\s*(?:CÂU BÀN GIAO|LỜI TUYÊN BỐ).*', card)
    print(f"\n=== Card {i}: {header} ===")
    print(f"  - Bullets count: {len(bullets)} (Requirement: 3-4 bullets)")
    for b_idx, b in enumerate(bullets, 1):
        clean_b = ' '.join(b.replace('│', ' ').split())
        print(f"    Bullet {b_idx}: {clean_b[:90]}...")
    print(f"  - Poster anchor: {len(neo) > 0}")
    print(f"  - Handover prompt: {len(handover) > 0}")
