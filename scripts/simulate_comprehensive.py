import re

with open('docs/assignment/PRESENTATION_SCRIPT_5W1H_SERVICE.md', 'r', encoding='utf-8') as f:
    text = f.read()

s1 = re.search(r's1 = """(.*?)"""', text, re.DOTALL).group(1)
s2 = re.search(r's2 = """(.*?)"""', text, re.DOTALL).group(1)
s3 = re.search(r's3 = """(.*?)"""', text, re.DOTALL).group(1)
s4 = re.search(r's4 = """(.*?)"""', text, re.DOTALL).group(1)
s5 = re.search(r's5 = """(.*?)"""', text, re.DOTALL).group(1)
s6 = re.search(r's6 = """(.*?)"""', text, re.DOTALL).group(1)

# In the verbatim text in Section II, check for explicit stage directions
# e.g., CEO: [Dừng 1 giây, ánh mắt đồng cảm nhìn bao quát hội trường]
# SP5: [Dừng 1 giây, ánh mắt kiên định nhìn thẳng Ban giám khảo]
# SP6: [giữ điểm chỉ trong đúng 3 giây], bow 3s
explicit_stage_pauses = {
    "Speaker 1 (CEO)": 1.0 + 1.0, # opening bow 1s + [Dừng 1s]
    "Speaker 2 (Product Lead)": 0.0,
    "Speaker 3 (Marketing Lead)": 0.0,
    "Speaker 4 (CX Lead)": 0.0,
    "Speaker 5 (Quality & Risk Lead)": 1.0, # [Dừng 1s]
    "Speaker 6 (PR & Comms Lead)": 3.0 + 3.0 # [giữ điểm chỉ 3s] + closing bow 3s
}

transition_delay_per_speaker = 2.0 # step up, smile, breathe

speakers = [
    ("Speaker 1 (CEO)", s1),
    ("Speaker 2 (Product Lead)", s2),
    ("Speaker 3 (Marketing Lead)", s3),
    ("Speaker 4 (CX Lead)", s4),
    ("Speaker 5 (Quality & Risk Lead)", s5),
    ("Speaker 6 (PR & Comms Lead)", s6)
]

print("="*85)
print("COMPREHENSIVE MULTI-FACTOR REALISTIC STAGE SIMULATION")
print("="*85)

for wpm in [130, 125, 120]:
    print(f"\n>>> SIMULATION AT {wpm} WPM (Standard Presentation Pace) <<<")
    total_team_time = 0.0
    for name, s in speakers:
        wc = len(s.split())
        commas = s.count(',')
        periods = len(re.findall(r'[\.\?\!](?:\s|$)', s))
        emdashes = s.count('—')
        
        punct_pause = (commas * 0.5) + (periods * 1.0) + (emdashes * 1.5)
        speech_time = (wc / wpm) * 60.0
        stage_pause = explicit_stage_pauses[name]
        trans_buf = transition_delay_per_speaker
        
        total_speaker_time = speech_time + punct_pause + stage_pause + trans_buf
        total_team_time += total_speaker_time
        
        print(f"{name:<30}: Speech={speech_time:5.1f}s | Punct={punct_pause:4.1f}s | Stage={stage_pause:3.1f}s | Trans={trans_buf:3.1f}s | TOTAL={total_speaker_time:5.1f}s ({total_speaker_time/60:.2f}m)")
    
    over_team = total_team_time - 720.0
    print(f"--> TEAM TOTAL: {total_team_time:.1f}s = {int(total_team_time//60)}m {int(total_team_time%60)}s | OVER RUN: +{over_team:.1f}s (+{over_team/60:.2f} minutes!)")
