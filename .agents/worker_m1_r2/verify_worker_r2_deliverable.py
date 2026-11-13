# -*- coding: utf-8 -*-
"""Comprehensive Verification Suite for Worker M1_R2 Deliverable:
PRESENTATION_SCRIPT_5W1H_SERVICE.md
"""
import os
import re
import sys

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

TARGET_FILE = os.path.abspath(r"c:\Users\MSI\Desktop\Final Market Pulse\docs\assignment\PRESENTATION_SCRIPT_5W1H_SERVICE.md")

def test_all():
    print("=" * 80)
    print("COMPREHENSIVE AUDIT OF PRESENTATION_SCRIPT_5W1H_SERVICE.md")
    print("=" * 80)
    
    assert os.path.exists(TARGET_FILE), f"File not found: {TARGET_FILE}"
    with open(TARGET_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    # --- 1. VERBATIM WORD COUNT AUDIT ---
    print("\n--- 1. VERBATIM WORD COUNT AUDIT ---")
    speaker_pattern = r"### 2\.([1-6])\s+Diễn Giả [1-6].*?#### B\.\s+Lời Thoại Thực Chiến Nguyên Văn.*?\n\n((?:> [^\n]*\n*)+)"
    matches = list(re.finditer(speaker_pattern, content, re.DOTALL))
    assert len(matches) == 6, f"Expected 6 speakers in Section 2, found {len(matches)}"
    
    total_words = 0
    expected_wcs = {1: 270, 2: 275, 3: 267, 4: 269, 5: 261, 6: 272}
    spoken_dialogs = {}
    
    for m in matches:
        num = int(m.group(1))
        raw_quote = m.group(2)
        lines = [l.strip()[1:].strip() if l.strip().startswith(">") else l.strip() for l in raw_quote.splitlines() if l.strip()]
        full_text = " ".join(lines)
        spoken_only = re.sub(r"\*\*\[.*?\]\*\*", "", full_text)
        spoken_only = re.sub(r"\[.*?\]", "", spoken_only)
        spoken_clean = spoken_only.replace("**", "").replace("*", "")
        spoken_clean = re.sub(r"\s+", " ", spoken_clean).strip().strip('"').strip("'").strip('“').strip('”')
        wc = len(spoken_clean.split())
        total_words += wc
        spoken_dialogs[num] = spoken_clean
        print(f"  Speaker {num}: {wc} words (Expected: {expected_wcs[num]})")
        assert 240 <= wc <= 280, f"Speaker {num} word count {wc} out of range [240, 280]"
        assert wc == expected_wcs[num], f"Speaker {num} word count {wc} != {expected_wcs[num]}"
    
    print(f"  Total Words: {total_words} (Expected: 1614)")
    assert total_words == 1614, f"Total word count {total_words} != 1614"
    print("  -> WORD COUNT AUDIT: PASS (100%)")

    # --- 2. ZERO BACKEND JARGON AUDIT ---
    print("\n--- 2. PROHIBITED JARGON AUDIT ---")
    banned_terms = [
        'sqlite', 'wal', 'qaoa', 'pennylane', 'piotroski', 'altman', 
        'microservice', 'backend', 'rag', 'api', 'gateway', 'qubit', 
        'hamiltonian', 'pauli', 'python', 'hotfix', 'bn-06', 'bn-07', 
        'sarimax', 'tokenizer', 'json', 'docker', 'kubernetes',
        'rest api', 'sql', 'database', 'vectorization', 'prompt injection'
    ]
    # Check Section 2 verbatim scripts
    for num, text in spoken_dialogs.items():
        for term in banned_terms:
            assert not re.search(rf"\b{re.escape(term)}\b", text.lower()), f"Banned jargon '{term}' in Speaker {num} speech!"
    print("  ✓ Verbatim spoken dialogue (Speakers 1-6): 0 prohibited terms found.")

    # Check Section 3 Cue Cards
    sec3_match = re.search(r"## PHẦN III:.*?(?=## PHẦN IV:)", content, re.DOTALL)
    assert sec3_match, "Section III not found"
    sec3 = sec3_match.group(0)
    for term in banned_terms:
        assert not re.search(rf"\b{re.escape(term)}\b", sec3.lower()), f"Banned jargon '{term}' in Section III Cue Cards!"
    print("  ✓ Section 3 Cue Cards: 0 prohibited terms found.")

    # Check Section 4 Transitions
    sec4_match = re.search(r"## PHẦN IV:.*?(?=## PHẦN V:)", content, re.DOTALL)
    assert sec4_match, "Section IV not found"
    sec4 = sec4_match.group(0)
    for term in banned_terms:
        assert not re.search(rf"\b{re.escape(term)}\b", sec4.lower()), f"Banned jargon '{term}' in Section IV Transitions!"
    print("  ✓ Section 4 Transitions: 0 prohibited terms found.")
    print("  -> ZERO BACKEND JARGON AUDIT: PASS (Spoken verbatim, cues, transitions 100% clean)")

    # --- 3. SECTION 1.3 ACOUSTIC MASTER TIMELINE AUDIT ---
    print("\n--- 3. ACOUSTIC MASTER TIMELINE AUDIT (Section 1.3) ---")
    assert "### 1.3 Bảng Tiến Trình Thời Gian & Mô Hình Âm Học Toàn Diện Từng Giây (Acoustic Master Timeline)" in content
    assert "Mô hình Âm học Nhịp Cụm Hơi (Prosodic Breath-Group Model)" in content
    assert "135 – 140 từ/phút (Trung bình tối ưu: 138 từ/phút = 2.30 âm tiết/giây)" in content
    assert "719.7s (11m 59.7s)" in content or "719.7s" in content
    assert "ĐÚNG 12 PHÚT 00 GIÂY" in content
    assert "117.4s" in content # SP1 pure
    assert "119.6s" in content # SP2 pure
    assert "116.1s" in content # SP3 pure
    assert "117.0s" in content # SP4 pure
    assert "113.5s" in content # SP5 pure
    assert "118.3s" in content # SP6 pure
    print("  -> SECTION 1.3 TIMELINE AUDIT: PASS")

    # --- 4. SECTION III MASTER CUE CARDS AUDIT ---
    print("\n--- 4. MASTER CUE CARDS AUDIT (Section III) ---")
    cards = re.findall(r"(\[CUE CARD \d+\].*?)(?=(?:\[CUE CARD \d+\]|```))", sec3, re.DOTALL)
    assert len(cards) == 6, f"Expected 6 cards, found {len(cards)}"
    
    # Card 1 has OPENING CUE
    assert "MỞ MÀN (OPENING CUE)" in cards[0]
    # Cards 2-6 have INCOMING HOOK
    for i in range(1, 6):
        assert "VÀO BÀI (INCOMING HOOK)" in cards[i], f"Card {i+1} missing INCOMING HOOK"
    
    # All cards have 2-line trigger handover
    for i, c in enumerate(cards, 1):
        assert "[Ý niệm]" in c, f"Card {i} missing [Ý niệm] trigger"
        assert "[Khẩu lệnh & Cử chỉ]" in c, f"Card {i} missing [Khẩu lệnh & Cử chỉ]"
        bullets = re.findall(r"│\s*•\s*(BULLET\s*\d+.*?)(?=(?:│\s*•|│\s*───|│\s*➔))", c, re.DOTALL)
        assert len(bullets) == 4, f"Card {i} bullets count {len(bullets)} != 4"
        neo = re.findall(r"│\s*•\s*ĐIỂM NEO.*", c)
        assert len(neo) > 0, f"Card {i} missing poster anchor"
        print(f"  Card {i}: 4 bullets, Poster anchor=True, Hook=True, 2-line Trigger=True")
    print("  -> SECTION III CUE CARDS AUDIT: PASS")

    # --- 5. SECTION 5.1 & 5.2 STAGE GEOMETRY & CHOREOGRAPHY AUDIT ---
    print("\n--- 5. STAGE GEOMETRY & CHOREOGRAPHY AUDIT (Section 5.1 & 5.2) ---")
    assert "### 5.1 Sơ Đồ Hình Học Sân Khấu Bất Đối Xứng (Asymmetric Open Crescent & 35° Easel Geometry)" in content
    assert "Xoay góc 35° hướng tâm" in content
    assert "GIÁ VẼ EASEL A0" in content
    assert "ĐỘI HÌNH CÁNH CUNG MỞ" in content
    assert "BỤC NÓI TIÊU ĐIỂM" in content
    assert "100% TẦM NHÌN TRỰC DIỆN POSTER" in content
    assert "100% TẦM NHÌN TRỰC DIỆN 6 DIỄN GIẢ" in content
    assert "Quy tắc Tam giác Thị giác Điều hành 60-30-10 (The 60-30-10 Executive Gaze Rule)" in content
    assert "Kỷ luật \"Touch, Turn, Talk\" & Điểm neo Thị giác 3 Giây" in content
    assert "TOUCH (Chạm Điểm Neo — Đúng 0.5 giây)" in content
    assert "TURN (Quay Đầu & Ánh Mắt Lại — Chuyển tức thì)" in content
    assert "TALK & HOLD (Thuyết Minh & Giữ Tĩnh Tay — Trọn vẹn 2.5 giây tiếp theo)" in content
    assert "Nghi thức Cúi chào Đồng bộ 5 Pha với Phách Lấy Đà Âm Học" in content
    assert "Pha 1 (Tập hợp đội hình & Dứt câu)" in content
    assert "Pha 2 (Phách lấy đà âm học — Acoustic Conductor Breath)" in content
    assert "Pha 3 (Cúi gập 15 độ đồng thời — 0.5s)" in content
    assert "Pha 4 (Bộ đếm thầm tĩnh lặng 3 giây — \"MỘT - HAI - BA\")" in content
    assert "Pha 5 (Nâng người đồng loạt & Nụ cười tự tin — 0.8s)" in content
    assert "Kỹ Thuật Ngắt Nghỉ Theo Cụm Hơi Ngữ Điệu (Prosodic Breath-Group Phrasing Rule)" in content
    assert "Bàn Giao Nhịp Cầu Không Khoảng Lặng (Zero-Latency Overlapping Baton Handover)" in content
    print("  -> SECTION 5.1 & 5.2 STAGE CHOREOGRAPHY AUDIT: PASS")

    # --- 6. SECTION 6.4 STAGE CLOCK MANAGEMENT AUDIT ---
    print("\n--- 6. STAGE CLOCK MANAGEMENT AUDIT (Section 6.4) ---")
    assert "### 6.4 Quy Tắc Quản Trị Đồng Hồ Sân Khấu Từng Giây & Kịch Bản Diễn Tập (Stage Clock Management & Rehearsal Playbook)" in content
    assert "Hệ Thống 4 Mốc Kiểm Soát Nhịp Tim Sân Khấu (4-Point Stage Clock Checkpoints)" in content
    assert "Mốc 0:30 (Mở bài / Hook)" in content
    assert "Mốc 1:00 (Nửa bài / Cốt lõi)" in content
    assert "Mốc 1:30 (Tăng tốc / Tiện ích cuối)" in content
    assert "Mốc 1:55 – 2:00 (Bàn giao hoàn tất)" in content
    assert "Bộ Điều Tốc Tức Thời (Dynamic Realtime Cadence Governor: 132 – 142 WPM)" in content
    assert "Giao Thức Báo Hiệu Đồng Đội Kín Đáo (Silent Stage Signaling Protocol)" in content
    print("  -> SECTION 6.4 STAGE CLOCK MANAGEMENT AUDIT: PASS")

    print("\n" + "=" * 80)
    print("ALL AUDIT VERIFICATIONS PASSED WITH 100% COMPLIANCE!")
    print("=" * 80)

if __name__ == "__main__":
    test_all()
