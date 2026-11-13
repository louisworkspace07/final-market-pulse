
import sys, os, re
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath('.'))
from scripts.challenge_5w1h_presentation import load_file, extract_section2_scripts

content = load_file()
speakers = extract_section2_scripts(content)

print(f'=== 1. SPOKEN TEXT ACOUSTIC AUDIT FOR {len(speakers)} SPEAKERS ===')
for num in sorted(speakers.keys()):
    sp = speakers[num]
    spoken = sp['spoken_clean']
    words = spoken.split()
    wc = len(words)
    commas = spoken.count(',')
    periods = spoken.count('.') + spoken.count('!') + spoken.count('?')
    title = sp['title']
    status = 'PASS' if 240 <= wc <= 280 else 'FAIL'
    print(f'Speaker {num} ({title[:18]}): {wc} words | {commas} commas, {periods} terminators | Status: {status}')

print('\n=== 2. PROSODIC BREATH-GROUP MODEL EVALUATION ===')
total_duration = 0.0
for num in sorted(speakers.keys()):
    sp = speakers[num]
    wc = len(sp['spoken_clean'].split())
    vocal = wc / 138.0 * 60.0
    breaths = 6 if num in [1, 5] else 7
    resp = breaths * 0.40
    dram = 1.0 if num in [1, 5] else 0.0
    tot = vocal + resp + dram
    total_duration += tot
    mins = int(tot // 60)
    secs = tot % 60
    stat = 'PASS' if 110 <= tot <= 130 else 'FAIL'
    print(f'Speaker {num}: {wc}w -> Vocal: {vocal:5.1f}s + Resp: {resp:3.1f}s + Dram: {dram:3.1f}s = {tot:5.1f}s ({mins}m {secs:04.1f}s) | Target: 110-130s -> {stat}')

tot_mins = int(total_duration // 60)
tot_secs = total_duration % 60
print(f'\nTEAM CUMULATIVE TIME: {total_duration:5.1f}s ({tot_mins}m {tot_secs:04.1f}s) | Target: 720.0s (12m 00s)')
assert 715 <= total_duration <= 725, f'Cumulative duration out of bounds: {total_duration}'
print('TEAM TIMING: PERFECT 12m00s CONFORMANCE!')

print('\n=== 3. MONTE CARLO SPEECH CADENCE & PAUSE STRESS TEST (1,000 RUNS) ===')
np.random.seed(42)
n_runs = 1000
team_durations = []
speaker_durations = {i: [] for i in range(1, 7)}

for run in range(n_runs):
    current_team_time = 0.0
    for num in sorted(speakers.keys()):
        sp = speakers[num]
        wc = len(sp['spoken_clean'].split())
        wpm = np.random.normal(138.0, 3.0)
        wps = wpm / 60.0
        vocal_time = wc / wps
        n_breaths = 6 if num in [1, 5] else 7
        breath_time = np.sum(np.random.normal(0.40, 0.04, n_breaths))
        dram_time = np.random.normal(1.0, 0.10) if num in [1, 5] else 0.0
        tot_sp = vocal_time + breath_time + dram_time
        speaker_durations[num].append(tot_sp)
        current_team_time += tot_sp
    team_durations.append(current_team_time)

team_durations = np.array(team_durations)
print(f'Team Total Duration (mean +- std): {np.mean(team_durations):.1f}s +- {np.std(team_durations):.1f}s')
print(f'Team Total in minutes: {np.mean(team_durations)/60:.2f}m (min: {np.min(team_durations)/60:.2f}m, max: {np.max(team_durations)/60:.2f}m)')
pass_rate = np.mean((team_durations >= 705) & (team_durations <= 735)) * 100
print(f'Probability of finishing between 11m45s and 12m15s: {pass_rate:.1f}%')

print('\nSpeaker Breakdown (Monte Carlo 95% Confidence Interval):')
for num in sorted(speakers.keys()):
    arr = np.array(speaker_durations[num])
    low, high = np.percentile(arr, [2.5, 97.5])
    sp_pass = np.mean((arr >= 110) & (arr <= 130)) * 100
    print(f'Speaker {num}: Mean = {np.mean(arr):5.1f}s | 95% CI = [{low:5.1f}s, {high:5.1f}s] | Compliant 110-130s: {sp_pass:5.1f}%')
