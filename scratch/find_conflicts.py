def search(filename):
    print(f"\n=== Conflicts in {filename} ===")
    with open(filename, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    for idx, line in enumerate(lines):
        if '<<<<<<<' in line or '=======' in line or '>>>>>>>' in line:
            print(f"Line {idx+1}: {line.strip()}")
            # Print context
            start = max(0, idx - 5)
            end = min(len(lines), idx + 6)
            print("--- context ---")
            for c_idx in range(start, end):
                marker = "-> " if c_idx == idx else "   "
                print(f"{marker}{c_idx+1}: {lines[c_idx]}", end="")
            print("---------------")

search("api/company_router.py")
search("pipeline/query.py")
