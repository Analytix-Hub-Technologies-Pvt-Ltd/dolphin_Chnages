import random
import re
from typing import List

OUT_OF_SCOPE_MESSAGES: List[str] = [
    "This topic is not covered in the available course material. Please ask a question related to the Marine/Maritime course content.",
    "This question falls outside the available course material. Please ask something related to the Marine/Maritime course topics.",
    "The requested information is not included in the current course content. Please ask a question relevant to the Marine/Maritime curriculum.",
]

def get_random_out_of_scope_message() -> str:
    """Return one of the standard out-of-scope messages chosen randomly."""
    return random.choice(OUT_OF_SCOPE_MESSAGES)

def is_out_of_scope_text(text: str) -> bool:
    """Check if the provided response text matches any out-of-scope message or pattern."""
    if not text or not isinstance(text, str):
        return False
    if any(msg in text for msg in OUT_OF_SCOPE_MESSAGES):
        return True
    legacy_phrases = [
        "not part of the available course material",
        "not covered in the available course material",
        "falls outside the available course material",
        "not included in the current course content",
        "related to the Marine/Maritime course",
        "relevant to the Marine/Maritime curriculum",
    ]
    return any(p in text for p in legacy_phrases)

def normalize_markdown_tables(text: str) -> str:
    """
    Ensure all tables, tabular checklists, tab-separated rows, space-separated rows,
    and pipe rows with missing separator lines are normalized to valid GFM Markdown tables.
    """
    if not text:
        return ""

    lines = text.split("\n")
    result_lines = []
    
    in_table = False
    table_cols = 0

    for i, line in enumerate(lines):
        trimmed = line.strip()

        if not trimmed:
            in_table = False
            table_cols = 0
            result_lines.append("")
            continue

        # Check if line is already a markdown pipe row
        is_pipe_row = trimmed.startswith("|") and trimmed.endswith("|") and len(trimmed) > 2
        is_pipe_separator = is_pipe_row and bool(re.match(r'^\|(?:\s*:?-+:?\s*\|)+$', trimmed))

        # Check if line is a heading, list item, or quote
        is_markdown_element = trimmed.startswith(("#", "-", "*", ">")) or bool(re.match(r'^\d+\.', trimmed))

        # Extract cells from pipe row or whitespace/tab separated row
        cells = []
        if is_pipe_row:
            if is_pipe_separator:
                result_lines.append(trimmed)
                continue
            cells = [c.strip() for c in trimmed[1:-1].split("|")]
        elif not is_markdown_element:
            if "\t" in line:
                cells = [c.strip() for c in line.split("\t")]
            elif re.search(r'\S\s{2,}\S', trimmed):
                cells = [c.strip() for c in re.split(r'\s{2,}', trimmed)]
            elif in_table:
                # Sub-heading or single cell row inside an active table (e.g. "During Maintenance")
                cells = [trimmed]

        # Determine if this should be a table row
        if len(cells) >= 2 or (in_table and len(cells) == 1):
            if not in_table:
                in_table = True
                table_cols = max(len(cells), 2)
                
                while len(cells) < table_cols:
                    cells.append("")
                md_header = f"| {' | '.join(cells)} |"
                # Check if next line is already a separator
                next_line = lines[i + 1].strip() if i + 1 < len(lines) else ""
                next_is_sep = next_line.startswith("|") and bool(re.match(r'^\|(?:\s*:?-+:?\s*\|)+$', next_line))
                
                result_lines.append(md_header)
                if not next_is_sep:
                    md_sep = f"| {' | '.join(['---'] * table_cols)} |"
                    result_lines.append(md_sep)
            else:
                while len(cells) < table_cols:
                    cells.append("")
                md_row = f"| {' | '.join(cells[:table_cols])} |"
                result_lines.append(md_row)
        else:
            in_table = False
            table_cols = 0
            result_lines.append(line)

    return "\n".join(result_lines)
