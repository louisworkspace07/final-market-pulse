import sys, re
sys.stdout.reconfigure(encoding='utf-8')

# Let's inspect the actual breath-group distribution in Vietnamese presentation speech
# In standard Vietnamese phonology (Cao Xuan Hao, Hoang Thi Quynh Hoa):
# Speech is organized into Prosodic Phrases / Breath Groups (Nhom hoi / Ngu doan ngu dieu).
# An energetic speaker takes a breath every 30-40 syllables (words), corresponding to major clause boundaries.
# Within a breath group, phonation is CONTINUOUS (lien tuc, khong co khoang lang / zero dead silence).
# Comma inside a breath group produces intonational contour shift (elevation of tone or slight mora prolongation of 50-80ms), NOT respiratory silence.

# Let's count actual breath groups in each speaker's script:
# A speaker takes a breath at:
# - Major sentence boundaries (not short transitional sentences)
# - Major rhetorical breaks

# Let's test different breath-group models:

scripts_data = [
    ("SP1 (CEO)", 270, 6, 1.0),       # 6 natural breath groups + 1 dramatic pause
    ("SP2 (Product)", 275, 7, 0.0),   # 7 natural breath groups (intro + 4 features + transition)
    ("SP3 (Marketing)", 267, 7, 0.0), # 7 natural breath groups (intro + 4 moments + 3 channels + bridge)
    ("SP4 (CX Lead)", 269, 7, 0.0),    # 7 natural breath groups (intro + 3 steps + 24/7 + bridge)
    ("SP5 (Risk Lead)", 261, 6, 1.0), # 6 natural breath groups + 1 dramatic pause
    ("SP6 (PR Lead)", 272, 7, 0.0),   # 7 natural breath groups (intro + vision + 0-dong + CTA + thanks)
]

print("="*105)
print("REALISTIC BREATH-GROUP PHONOLOGY MODEL (VIETNAMESE BUSINESS SPEECH CADENCE)")
print("="*105)

for wpm in [135, 138, 140]:
    print(f"\n--- CADENCE: {wpm} WPM (Phonation Rate = {wpm/60:.2f} syllables/sec) ---")
    total_time = 0.0
    for name, wc, breath_groups, dram_pause in scripts_data:
        phonation = (wc / wpm) * 60.0
        # Each breath group boundary requires a physiological inhalation of 0.40s
        breath_time = breath_groups * 0.40
        sp_time = phonation + breath_time + dram_pause
        total_time += sp_time
        print(f"{name:<20} | WC={wc:3d} | Phonation={phonation:5.1f}s | Breaths ({breath_groups}x0.4s)={breath_time:4.1f}s | Dram={dram_pause:3.1f}s | TOTAL={sp_time:5.1f}s ({sp_time/60:.2f}m)")
    
    print(f"--> CUMULATIVE TEAM DURATION @ {wpm} WPM: {total_time:.1f}s = {int(total_time//60)}m {int(total_time%60):02d}s (Delta vs 720s: {total_time - 720.0:+4.1f}s)")
