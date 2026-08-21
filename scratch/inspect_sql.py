from pathlib import Path

def inspect_sql():
    sql_path = Path(r"C:\Users\HP\Downloads\dolphin-db\dolphin-db.sql")
    print(f"Checking if file exists: {sql_path.exists()}")
    if not sql_path.exists():
        return
    
    size = sql_path.stat().st_size
    print(f"File size: {size / (1024 * 1024):.2f} MB")
    
    # Let's find insert statements for company_documents
    print("Searching for company_documents references in the SQL file...")
    found_lines = []
    with open(sql_path, "r", encoding="utf-8", errors="ignore") as f:
        for idx, line in enumerate(f, 1):
            if "company_documents" in line:
                found_lines.append((idx, line.strip()))
                if len(found_lines) >= 30:
                    print("Found more than 30 lines, stopping search.")
                    break
    
    for idx, line in found_lines:
        print(f"Line {idx}: {line[:200]}")

if __name__ == "__main__":
    inspect_sql()
