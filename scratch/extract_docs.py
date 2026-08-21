import os
from pathlib import Path

def find_pg_restore_anywhere():
    search_dirs = [
        Path("C:/Program Files"),
        Path("C:/Program Files (x86)"),
        Path("C:/Users/HP/AppData/Local"),
    ]
    
    print("Scanning folders for pg_restore.exe...")
    found = []
    for sdir in search_dirs:
        if not sdir.exists():
            continue
        print(f"Scanning {sdir}...")
        try:
            for root, dirs, files in os.walk(sdir):
                # Avoid walking too deep into massive node_modules/git directories if possible, but standard directories should be fine
                if "pg_restore.exe" in files:
                    p = Path(root) / "pg_restore.exe"
                    found.append(p)
                    print(f"FOUND: {p}")
        except Exception as e:
            print(f"Error scanning {sdir}: {e}")
            
    print(f"Done. Found: {found}")

if __name__ == "__main__":
    find_pg_restore_anywhere()
