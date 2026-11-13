import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

DOC_PATH = r'docs/assignment/PRESENTATION_SCRIPT_5W1H_SERVICE.md'
with open(DOC_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

# Let's check Section 1, Section 2, Section 3, Section 4, Section 5, Section 6
# Where do technical terms appear? They are expected in Section 6.2 (where banned terms are audited in the table).
# But what about Sections 1, 2, 3, 4, 5?
sections = re.split(r'## PHẦN ', content)
print(f"Total major sections: {len(sections)-1}")

banned_jargon = [
    'sqlite', 'wal', 'qaoa', 'pennylane', 'piotroski', 'altman', 
    'microservice', 'backend', 'rag', 'api', 'gateway', 'qubit', 
    'hamiltonian', 'pauli', 'python', 'hotfix', 'bn-06', 'bn-07', 
    'sarimax', 'tokenizer', 'json'
]

for idx, sec in enumerate(sections[1:], 1):
    sec_name = sec.splitlines()[0]
    print(f"\n--- Checking PHẦN {idx}: {sec_name} ---")
    found_in_sec = {}
    sec_lower = sec.lower()
    for bj in banned_jargon:
        count = len(re.findall(rf'\b{re.escape(bj)}\b', sec_lower))
        if count > 0:
            found_in_sec[bj] = count
    if found_in_sec:
        print(f"  Terms found: {found_in_sec}")
    else:
        print("  Clean! No banned jargon found.")
