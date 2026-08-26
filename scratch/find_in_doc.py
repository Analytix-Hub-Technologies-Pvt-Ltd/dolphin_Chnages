import os

with open("scratch/doc_content_cow.txt", "r", encoding="utf-8") as f:
    lines = f.readlines()

search_terms = ["washing", "cow", "cleaning"]

for idx, line in enumerate(lines):
    line_lower = line.lower()
    for term in search_terms:
        if term in line_lower:
            print(f"Line {idx+1}: {line.strip()[:120]}")
            break
