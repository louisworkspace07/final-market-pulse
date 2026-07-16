# -*- coding: utf-8 -*-
"""Bóc claim từ đoạn text tin đồn người dùng dán vào Soi Tin.

Input: 1 đoạn văn (tin đồn/tít báo, có thể nhiều câu, không dấu, teencode).
Output: list[Claim] — mỗi claim gồm:
  - text     : câu gốc chứa nhận định;
  - symbols  : mã CK liên quan (qua modules.common.vitext);
  - kind     : loại claim (dividend/earnings/issuance/ma/delist/insider/
               price_target/macro/other) — dùng để checker biết bảng nào cần soi.

Không gọi AI: tách câu bằng dấu câu + heuristic từ khóa. Bóc thô nhưng đủ để
checker/engine đối chiếu; AI ở engine mới diễn giải sâu.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict

from modules.common import vitext

# Ngưỡng câu quá ngắn (lời dẫn "nghe nói", "có tin") → gộp vào câu sau.
_MIN_CLAIM_LEN = 12

# Từ khóa (đã normalize không dấu) → loại claim. Xét theo thứ tự, khớp đầu tiên.
_KIND_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("dividend",     ("co tuc", "chia thuong", "tra thuong", "co phieu thuong")),
    ("issuance",     ("phat hanh them", "phat hanh co phieu", "tang von", "chao ban",
                      "phat hanh rieng le")),
    ("ma",           ("sap nhap", "thau tom", "mua lai", "bat tay", "hop tac",
                      "co dong chien luoc", "rot von", "lien doanh")),
    ("delist",       ("huy niem yet", "roi san", "dinh chi giao dich", "canh bao",
                      "kiem soat")),
    ("insider",      ("noi bo", "co dong lon", "ban ra", "mua vao", "dang ky ban",
                      "dang ky mua", "giao dich noi bo")),
    ("earnings",     ("loi nhuan", "lai rong", "lai khung", "lai ky luc", "doanh thu",
                      "bao lai", "bao lo", "thua lo", "ket qua kinh doanh", "bctc",
                      "bao cao tai chinh", "gian lan")),
    ("price_target", ("gia muc tieu", "tang tran", "giam san", "ve gia", "len gia",
                      "x2", "x3", "an bang lan", "song", "but pha")),
    ("macro",        ("ty gia", "lai suat", "lam phat", "gdp", "room tin dung",
                      "chinh sach", "fed", "ngan hang nha nuoc", "sbv")),
]


@dataclass
class Claim:
    text: str
    symbols: list[str] = field(default_factory=list)
    kind: str = "other"

    def to_dict(self) -> dict:
        return asdict(self)


def _classify(sentence_norm: str) -> str:
    for kind, kws in _KIND_RULES:
        if any(kw in sentence_norm for kw in kws):
            return kind
    return "other"


def _split_sentences(text: str) -> list[str]:
    """Tách câu theo . ! ? ; xuống dòng. Gộp mảnh quá ngắn vào câu kế tiếp."""
    parts = re.split(r"[.!?;\n]+", text or "")
    parts = [p.strip() for p in parts if p.strip()]
    merged: list[str] = []
    carry = ""
    for p in parts:
        cand = (carry + " " + p).strip() if carry else p
        if len(cand) < _MIN_CLAIM_LEN:
            carry = cand
            continue
        merged.append(cand)
        carry = ""
    if carry:
        if merged:
            merged[-1] = (merged[-1] + " " + carry).strip()
        else:
            merged.append(carry)
    return merged


def extract_claims(text: str) -> list[Claim]:
    """Bóc list Claim từ đoạn text. Câu không có nhận định gì → vẫn giữ (kind=other)."""
    claims: list[Claim] = []
    for sent in _split_sentences(text):
        norm = vitext.normalize(sent)
        claims.append(Claim(
            text=sent,
            symbols=vitext.find_symbols(sent),
            kind=_classify(norm),
        ))
    return claims


def all_symbols(claims: list[Claim]) -> list[str]:
    """Gom mọi mã CK xuất hiện trong các claim (giữ thứ tự, không trùng)."""
    seen: set[str] = set()
    out: list[str] = []
    for c in claims:
        for s in c.symbols:
            if s not in seen:
                seen.add(s)
                out.append(s)
    return out


if __name__ == "__main__":
    import os
    fx = os.path.join(os.path.dirname(__file__), "..", "..", "tests", "fixtures", "rumors.txt")
    with open(fx, encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln or ln.startswith("#"):
                continue
            for c in extract_claims(ln):
                print(f"[{c.kind:12}] {c.symbols} :: {c.text[:60]}")
