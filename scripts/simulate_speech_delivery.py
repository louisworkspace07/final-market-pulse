import sys, re

with open('docs/assignment/PRESENTATION_SCRIPT_5W1H_SERVICE.md', 'r', encoding='utf-8') as f:
    content = f.read()

# Section 6.3 contains s1 through s6 strings
s1 = re.search(r's1 = """(.*?)"""', content, re.DOTALL).group(1)
s2 = re.search(r's2 = """(.*?)"""', content, re.DOTALL).group(1)
s3 = re.search(r's3 = """(.*?)"""', content, re.DOTALL).group(1)
s4 = re.search(r's4 = """(.*?)"""', content, re.DOTALL).group(1)
s5 = re.search(r's5 = """(.*?)"""', content, re.DOTALL).group(1)
s6 = re.search(r's6 = """(.*?)"""', content, re.DOTALL).group(1)

speakers = [
    ("Speaker 1 (CEO)", s1),
    ("Speaker 2 (Product Lead)", s2),
    ("Speaker 3 (Marketing Lead)", s3),
    ("Speaker 4 (CX Lead)", s4),
    ("Speaker 5 (Quality & Risk Lead)", s5),
    ("Speaker 6 (PR & Comms Lead)", s6)
]

print("="*80)
print("EMPIRICAL SPEECH DELIVERY SIMULATION WITH PUNCTUATION PAUSES")
print("Standard pause parameters:")
print("  - Comma (,): 0.5s")
print("  - Period/Question/Exclamation (./?/\!): 1.0s")
print("  - Em-dash (—): 1.5s")
print("="*80)

results = []

for name, s in speakers:
    words = s.split()
    wc = len(words)
    
    commas = s.count(',')
    # Sentence-ending punctuation: . ? !
    # Avoid counting decimal dots like 0–100 or 1.0, count periods followed by space or end
    periods = len(re.findall(r'[\.\?\!](?:\s|$)', s))
    emdashes = s.count('—')
    colons = s.count(':') + s.count(';')
    
    # Required pause model: 0.5s commas, 1.0s periods/exclamations/questions, 1.5s em-dashes
    pause_time = (commas * 0.5) + (periods * 1.0) + (emdashes * 1.5)
    
    # Also evaluate explicit stage cue pauses mentioned in section II
    # e.g., CEO has [Dừng 1 giây], SP5 has [Dừng 1 giây], SP6 has [giữ điểm chỉ 3 giây], closing bow 3s
    
    # Calculate for wpm = 130 (author claimed baseline), 125, 120, 140, 150
    # Note: If wpm includes articulation of syllables
    print(f"\n--- {name} ---")
    print(f"Word count: {wc} words")
    print(f"Punctuation counts: Commas={commas} ({commas*0.5:.1f}s) | Sentence-ends={periods} ({periods*1.0:.1f}s) | Em-dashes={emdashes} ({emdashes*1.5:.1f}s) | Colons/semicolons={colons}")
    print(f"Total pure punctuation pause time: {pause_time:.1f} seconds")
    
    rates = {}
    for wpm in [140, 130, 125, 120, 110]:
        pure_speech_time = (wc / wpm) * 60.0
        total_delivery_time = pure_speech_time + pause_time
        rates[wpm] = (pure_speech_time, total_delivery_time)
        status = "OK"
        if total_delivery_time > 120:
            status = f"OVER TIME (+{total_delivery_time - 120:.1f}s)"
        elif total_delivery_time < 100:
            status = f"UNDER TIME (-{100 - total_delivery_time:.1f}s)"
        print(f"  @ {wpm} WPM: Speech={pure_speech_time:.1f}s + Pause={pause_time:.1f}s = TOTAL {total_delivery_time:.1f}s ({total_delivery_time/60:.2f} min) -> [{status}]")
    
    results.append({
        'name': name,
        'wc': wc,
        'commas': commas,
        'periods': periods,
        'emdashes': emdashes,
        'pause_time': pause_time,
        'rates': rates
    })

print("\n" + "="*80)
print("AGGREGATE SUMMARY & THRESHOLD ANALYSIS (Target: 100s - 120s per speaker)")
print("="*80)
for r in results:
    t_130 = r['rates'][130][1]
    t_140 = r['rates'][140][1]
    t_120 = r['rates'][120][1]
    print(f"{r['name']:<30} | WC={r['wc']} | Pause={r['pause_time']:>4.1f}s | @130wpm: {t_130:>5.1f}s | @140wpm: {t_140:>5.1f}s | @120wpm: {t_120:>5.1f}s")
