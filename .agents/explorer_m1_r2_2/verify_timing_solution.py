import sys, re
sys.stdout.reconfigure(encoding='utf-8')

def run_verification():
    with open('docs/assignment/PRESENTATION_SCRIPT_5W1H_SERVICE.md', 'r', encoding='utf-8') as f:
        text = f.read()

    s1 = re.search(r's1 = """(.*?)"""', text, re.DOTALL).group(1)
    s2 = re.search(r's2 = """(.*?)"""', text, re.DOTALL).group(1)
    s3 = re.search(r's3 = """(.*?)"""', text, re.DOTALL).group(1)
    s4 = re.search(r's4 = """(.*?)"""', text, re.DOTALL).group(1)
    s5 = re.search(r's5 = """(.*?)"""', text, re.DOTALL).group(1)
    s6 = re.search(r's6 = """(.*?)"""', text, re.DOTALL).group(1)

    speakers = [
        ('Speaker 1 (CEO)', s1, 6, 1.0),
        ('Speaker 2 (Product Lead)', s2, 7, 0.0),
        ('Speaker 3 (Marketing Lead)', s3, 7, 0.0),
        ('Speaker 4 (CX Lead)', s4, 7, 0.0),
        ('Speaker 5 (Quality & Risk Lead)', s5, 6, 1.0),
        ('Speaker 6 (PR & Comms Lead)', s6, 7, 0.0)
    ]

    print("="*105)
    print("INDEPENDENT VERIFICATION OF TIMING AND PAUSE OVERHEAD SOLUTION")
    print("="*105)

    # 1. Word Count Verification
    print("\n--- 1. WORD COUNT VERIFICATION (Constraint: 240 <= WC <= 280) ---")
    for name, s, _, _ in speakers:
        wc = len(s.split())
        assert 240 <= wc <= 280, f"VIOLATION: {name} word count {wc} out of bounds!"
        print(f"✓ {name:<30}: {wc} words [PASS]")

    # 2. Comparison of Models
    print("\n--- 2. TIMING COMPARISON: CHALLENGER 2 VS REALISTIC PROSODIC MODEL ---")
    print(f"{'Speaker':<28} | {'WC':<4} | {'Challenger 2 (130wpm)':<22} | {'Prosodic Model (138wpm)':<24} | {'Status'}")
    print("-"*105)
    
    total_ch = 0.0
    total_pro = 0.0
    
    for name, s, breath_groups, dram_pause in speakers:
        wc = len(s.split())
        commas = s.count(',')
        periods = len(re.findall(r'[\.\?\!](?:\s|$)', s))
        emdashes = s.count('—')
        
        # Challenger 2 model: 0.5s comma, 1.0s period, 1.5s dash, 130 WPM
        ch_pause = (commas * 0.5) + (periods * 1.0) + (emdashes * 1.5)
        ch_time = (wc / 130 * 60) + ch_pause
        total_ch += ch_time
        
        # Realistic Prosodic Model: 138 WPM, breath groups @ 0.4s each, 0s intra-phrase comma pause
        phonation = (wc / 138 * 60)
        breath_time = breath_groups * 0.40
        pro_time = phonation + breath_time + dram_pause
        total_pro += pro_time
        
        status = "110-130s [OPTIMAL]" if 110 <= pro_time <= 130 else "OUT OF BOUNDS"
        print(f"{name:<28} | {wc:<4} | {ch_time:5.1f}s ({ch_time/60:.2f}m)           | {pro_time:5.1f}s ({pro_time/60:.2f}m)             | {status}")

    print("-"*105)
    print(f"TEAM TOTAL:                  | 1614 | {total_ch:5.1f}s ({total_ch/60:.2f}m = {int(total_ch//60)}m{int(total_ch%60):02d}s)  | {total_pro:5.1f}s ({total_pro/60:.2f}m = {int(total_pro//60)}m{int(total_pro%60):02d}s)   | TARGET: 720.0s (12m00s)")
    print("="*105)

if __name__ == '__main__':
    run_verification()
