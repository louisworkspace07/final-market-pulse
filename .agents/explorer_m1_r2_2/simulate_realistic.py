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
    ('Speaker 1 (CEO)', s1, 1.0), # 1 explicit dramatic pause of 1s
    ('Speaker 2 (Product Lead)', s2, 0.0),
    ('Speaker 3 (Marketing Lead)', s3, 0.0),
    ('Speaker 4 (CX Lead)', s4, 0.0),
    ('Speaker 5 (Quality & Risk Lead)', s5, 1.0), # 1 explicit dramatic pause of 1s
    ('Speaker 6 (PR & Comms Lead)', s6, 0.0) # gestures concurrent with speech
]

print("="*105)
print("REALISTIC ACOUSTIC SIMULATION WITH PHRASE BREATH-GROUPS & STAGE CONCURRENCY")
print("="*105)

# Test pacing across 135, 138, 140 WPM
for wpm in [135, 138, 140]:
    print(f"\n--- PACING SCENARIO: {wpm} WPM ---")
    team_total = 0.0
    for name, s, dram_pause in scripts:
        words = s.split()
        wc = len(words)
        commas = s.count(',')
        periods = len(re.findall(r'[\.\?\!](?:\s|$)', s))
        emdashes = s.count('—')
        
        # Acoustic parameters:
        # Intra-phrase micro-pause (comma): 0.20s
        # Respiration replenishment (period): 0.45s
        # Rhetorical dash: 0.50s
        acoustic_pause = (commas * 0.20) + (periods * 0.45) + (emdashes * 0.50) + dram_pause
        phonation_time = (wc / wpm) * 60.0
        total_time = phonation_time + acoustic_pause
        team_total += total_time
        
        print(f"{name:<28} | WC={wc:3d} | Phonation={phonation_time:5.1f}s | Pauses={acoustic_pause:4.1f}s | TOTAL={total_time:5.1f}s ({total_time/60:.2f}m)")
    
    diff_12m = team_total - 720.0
    print(f"--> TEAM TOTAL @ {wpm} WPM: {team_total:5.1f}s = {int(team_total//60)}m {int(team_total%60):02d}s (Delta vs 12m: {diff_12m:+4.1f}s)")

