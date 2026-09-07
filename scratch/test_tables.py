import re

def clean_table_line(raw_line):
    # Convert tab-separated to markdown table
    if '\t' in raw_line and not raw_line.startswith('|'):
        cells = [c.strip() for c in raw_line.split('\t') if c.strip()]
        if len(cells) >= 2:
            return "| " + " | ".join(cells) + " |"
        return raw_line
    
    if '|' in raw_line:
        # Standardize markdown table line
        parts = [c.strip() for c in raw_line.split('|')]
        # Drop empty prefix/suffix from leading/trailing pipe
        if raw_line.strip().startswith('|') and parts and parts[0] == '':
            parts.pop(0)
        if raw_line.strip().endswith('|') and parts and parts[-1] == '':
            parts.pop()
        # If line has cells
        if parts and any(p for p in parts):
            return "| " + " | ".join(parts) + " |"
    return raw_line

# Test sample tables
lines = [
    "| Equipment | Type | Numbers (Minimum) |",
    "| :--- | :--- | :---: |",
    "| Multi-gas detector | Portable (O2, LEL, H2S, CO) | 2 sets |",
    "| Toxic gas detector | Chemical reagent tube type | 1 set |",
    "| Activity\tResponsibility\tRemarks",
    "| Check lines\tChief Officer\tChief Officer"
]

for l in lines:
    print(clean_table_line(l))
