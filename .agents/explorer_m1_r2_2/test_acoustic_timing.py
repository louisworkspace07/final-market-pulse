import sys, re

with open('docs/assignment/PRESENTATION_SCRIPT_5W1H_SERVICE.md', 'r', encoding='utf-8') as f:
    text = f.read()

s1 = re.search(r's1 = """(.*?)"""', text, re.DOTALL).group(1)
s2 = re.search(r's2 = """(.*?)"""', text, re.DOTALL).group(1)
s3 = re.search(r's3 = """(.*?)"""', text, re.DOTALL).group(1)
s4 = re.search(r's4 = """(.*?)"""', text, re.DOTALL).group(1)
s5 = re.search(r's5 = """(.*?)"""', text, re.DOTALL).group(1)
s6 = re.search(r's6 = """(.*?)"""', text, re.DOTALL).group(1)

scripts = [
    ('SP1 (CEO)', s1),
    ('SP2 (Product Lead)', s2),
    ('SP3 (Marketing Lead)', s3),
    ('SP4 (CX Lead)', s4),
    ('SP5 (Quality & Risk Lead)', s5),
    ('SP6 (PR & Comms Lead)', s6)
]

print("="*95)
print("VIETNAMESE SPOKEN ACOUSTICS: REALISTIC CADENCE VS CHALLENGER 2'S FLAWED MODEL")
print("="*95)

total_nat_138 = 0
total_ch_130 = 0

for name, s in scripts:
    wc = len(s.split())
    commas = s.count(',')
    periods = len(re.findall(r'[\.\?\!](?:\s|$)', s))
    emdashes = s.count('—')
    
    # Model 1: Challenger 2 (Mechanical dead silences: 0.5s comma, 1.0s period, 1.5s dash, 130 WPM)
    ch_pause = commas * 0.5 + periods * 1.0 + emdashes * 1.5
    ch_time_130 = (wc / 130 * 60) + ch_pause
    total_ch_130 += ch_time_130
    
    # Model 2: Natural Vietnamese Pitch Cadence (Breath-group phrasing: 0.20s comma micro-pause, 0.50s period breath, 0.60s dash)
    nat_pause = commas * 0.20 + periods * 0.50 + emdashes * 0.60
    nat_time_138 = (wc / 138 * 60) + nat_pause
    nat_time_135 = (wc / 135 * 60) + nat_pause
    nat_time_140 = (wc / 140 * 60) + nat_pause
    total_nat_138 += nat_time_138
    
    print(f"{name:<28} | {wc} w | {commas:2d}c {periods:2d}p | Ch2: {ch_time_130:5.1f}s | Nat @138 WPM: {nat_time_138:5.1f}s | Range [135-140]: {nat_time_140:5.1f}s - {nat_time_135:5.1f}s")

print("-"*95)
print(f"Total Team Time @ Challenger 2 model (130 WPM + 0.5s/1.0s/1.5s): {total_ch_130:.1f}s = {total_ch_130/60:.2f} min")
print(f"Total Team Time @ Natural Vietnamese Pitch Cadence (138 WPM + breath-group): {total_nat_138:.1f}s = {total_nat_138/60:.2f} min ({int(total_nat_138//60)}m {int(total_nat_138%60)}s)")
print("="*95)
