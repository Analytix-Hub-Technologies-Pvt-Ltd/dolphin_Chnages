from __future__ import annotations

import re
from loguru import logger


def remove_unwanted_sections(text: str) -> str:
    """Detect and remove Company front page, Table of Contents, Revision sheet,
    Acknowledgement sheet, and Page Headers & Footers from document text prior to embedding.
    """
    if not text or not text.strip():
        logger.warning("Empty document text received for section removal.")
        logger.info("removal process is done")
        return ""

    logger.info("Starting section, header, and footer removal process...")
    logger.info("Input document length: {} characters, {} lines", len(text), len(text.splitlines()))

    lines = text.splitlines()
    cleaned_lines: list[str] = []

    in_unwanted_section = False
    unwanted_section_name: str | None = None
    is_at_document_start = True
    in_front_page_block = False

    # Statistics counters
    removed_header_footer_count = 0
    removed_front_page_lines = 0
    removed_toc_lines = 0
    removed_revision_lines = 0
    removed_acknowledgement_lines = 0

    # Flexible prefix allowing "A.", "B.", "1.", "Section A.", "Appendix 1", "[A]", etc.
    # Flexible prefix allowing "A.", "B.", "1.", "Section A.", "Appendix 1", "[A]", etc.
    prefix_pattern = r"(?:(?:section|appendix|part|chapter|chap)?\s*\(?[a-z0-9]{1,3}\)?[\.\:\-]?\s*|[#*\-=\s]*)*"

    # Standard headers for sections to remove
    toc_headers = re.compile(
        rf"^(?:[#*\-=\s]*)(?:(?:section|appendix|part|chapter|chap)?\s*\(?[a-z0-9]{1,3}\)?[\.\:\-]?\s*)*"
        rf"(?:table\s+of\s+contents|table\s+of\s+content|contents|index\s+of\s+tables|index\s+of\s+figures|list\s+of\s+tables|list\s+of\s+figures|t\.o\.c\.|index)\b",
        re.IGNORECASE,
    )
    revision_headers = re.compile(
        rf"^(?:[#*\-=\s]*)(?:(?:section|appendix|part|chapter|chap)?\s*\(?[a-z0-9]{1,3}\)?[\.\:\-]?\s*)*"
        rf"(?:revision\s+sheet|revision\s+history|record\s+of\s+revisions|record\s+of\s+amendments|document\s+control|document\s+revision|revision\s+log|revision\s+record|version\s+history|revision\s+control|revisions|revision)\b",
        re.IGNORECASE,
    )
    ack_headers = re.compile(
        rf"^(?:[#*\-=\s]*)(?:(?:section|appendix|part|chapter|chap)?\s*\(?[a-z0-9]{1,3}\)?[\.\:\-]?\s*)*"
        rf"(?:acknowledgement\s+sheet|acknowledgement|acknowledgements|acknowledgment\s+sheet|acknowledgment|acknowledgments)\b",
        re.IGNORECASE,
    )
    front_page_headers = re.compile(
        rf"^(?:[#*\-=\s]*)(?:(?:section|appendix|part|chapter|chap)?\s*\(?[a-z0-9]{1,3}\)?[\.\:\-]?\s*)*"
        rf"(?:company\s+front\s+page|front\s+cover|cover\s+page|title\s+page|document\s+cover)\b",
        re.IGNORECASE,
    )

    # Headers that indicate a real content section has started (exits unwanted section mode).
    # Matches "C. Abbreviations", "1. Introduction", "1.1 Scope", "Section 1", "Chapter 1", etc.
    content_headers = re.compile(
        r"^(?:[#*\-=\s]*)(?:(?:chapter|section|part|appendix)\s+[a-z0-9]+|[1-9]\d*(?:\.\d+)*[\.\:\-]?\s+[A-Za-z]+|abbreviations|introduction|executive\s+summary|overview|background|scope|purpose|system\s+description|architecture)\b",
        re.IGNORECASE,
    )

    # Specific check for lines that look like Table of Contents / Index entries
    toc_line_entry = re.compile(
        r"^(?:"
        r".{1,120}(?:\.{2,}|\_{2,}|\-{2,}|\s{3,}|\.\s\.\s\.)\s*(?:page\s*)?[a-z0-9\-\.\,\s\/]+|"
        r".{1,120}\s+(?:page\s*)[a-z0-9\-\.]+|"
        r".{1,120}\s+\d{1,4}\s*|"
        r"\s*\d+\s*page[s]?\s*\|.*|"
        r"\s*\|\s*.*?\s*\|\s*(?:Form:\s*[\w\(\)]+|\d+(?:\.\d+)+|[0-9][A-Z]|TOC)\s*|"
        r"\s*\|\s*.*?\s*\|\s*[\w\.\:\(\)\-]*\s*|"
        r"\s*\|\s*[^|]+(?:\s*\|\s*)?$|"
        r"\s*(?:0[0-9]|\d{1,2})\s*\|\s*(?:\|\s*)*$|"
        r"\s*(?:\|\s*)+$|"
        r"\s*[\*\-\+]?\s*\[.+\]\(#.+\)|"
        r".*\|\s*(?:toc|page[s]?|pages|\d+\s*pages)\b.*"
        r")$",
        re.IGNORECASE,
    )

    # Pattern for standalone revision entry lines containing dates, revision numbers, or revision table fields
    revision_line_entry = re.compile(
        r"^(?:"
        r".*\b(?:last|current)?\s*date\s*(?:&|and|\/)?\s*rev\.?\s*(?:no\.?|num)?.*|"
        r".*\b\d{2}[\.\/\-]\d{2}[\.\/\-]\d{4}(?:\s+\d{1,2})?\b.*|"
        r".*\b\d{4}[\.\/\-]\d{2}[\.\/\-]\d{2}\b.*|"
        r".*\b(?:rev|revision|ver|version)\.?\s*\d+(?:\.\d+)*\s*[\:\-\|].*|"
        r".*\|\s*(?:rev|revision|date|version)\b.*"
        r")$",
        re.IGNORECASE,
    )

    # Front page metadata lines at the start of document
    front_page_meta_line = re.compile(
        r"^(?:company|author|date|document\s+id|doc\s+ref|version|status|classification|prepared\s+by|approved\s+by|distribution|confidential|all\s+rights\s+reserved|page\s+1\s+of)\s*:\s*",
        re.IGNORECASE,
    )

    # Header and Footer line patterns (Page numbers, Running Headers/Footers, Confidentiality lines, Divider bars)
    header_footer_patterns = re.compile(
        r"^(?:"
        r"(?:header|footer)\s*:\s*.*|"
        r"\[?\s*(?:header|footer)\s*\]?.*|"
        r"page\s*[-:\#|]?\s*\d+(?:\s*(?:of|/|-)\s*\d+)?|"
        r"\d+\s*of\s*\d+\s*page[s]?|"
        r"-\s*\d+\s*-|"
        r"confidential(?:\s+and\s+proprietary)?(?:\s*-\s*for\s+internal\s+use\s+only)?|"
        r"all\s+rights\s+reserved\.?|"
        r"copyright\s*(?:©|\(c\))\s*\d{4}.*|"
        r"(?:safety\s+management\s+system\s+)?shipboard\s+sms\s+manual.*|"
        r"vol\.\s*[-–]\s*[ivx0-9]+\s*\(.*?\).*|"
        r"section\s+revised\s*\|.*|"
        r"[-=_]{5,}"
        r")$",
        re.IGNORECASE,
    )

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if not in_unwanted_section and not in_front_page_block:
                cleaned_lines.append(line)
            continue

        # Check for Header / Footer lines
        if header_footer_patterns.match(stripped):
            removed_header_footer_count += 1
            logger.info("Removing header/footer line: '{}'", stripped)
            continue

        lower_stripped = stripped.lower()

        # Check if line matches an unwanted section header (overrides any existing mode)
        is_front_header = bool(front_page_headers.match(stripped))
        is_rev_header = bool(revision_headers.match(stripped) or ("revision" in lower_stripped and "sheet" in lower_stripped and len(stripped) < 80))
        is_ack_header = bool(ack_headers.match(stripped) or ("acknowledgement" in lower_stripped and len(stripped) < 80) or ("acknowledgment" in lower_stripped and len(stripped) < 80))
        is_toc_header = bool(toc_headers.match(stripped))

        if is_front_header:
            in_unwanted_section = True
            unwanted_section_name = "Company Front Page"
            removed_front_page_lines += 1
            logger.info("Detected header: '{}' -> Removing section [{}]", stripped, unwanted_section_name)
            continue
        elif is_rev_header:
            in_unwanted_section = True
            unwanted_section_name = "Revision Sheet"
            removed_revision_lines += 1
            logger.info("Detected header: '{}' -> Removing section [{}]", stripped, unwanted_section_name)
            continue
        elif is_ack_header:
            in_unwanted_section = True
            unwanted_section_name = "Acknowledgement Sheet"
            removed_acknowledgement_lines += 1
            logger.info("Detected header: '{}' -> Removing section [{}]", stripped, unwanted_section_name)
            continue
        elif is_toc_header:
            in_unwanted_section = True
            unwanted_section_name = "Table of Contents"
            removed_toc_lines += 1
            logger.info("Detected header: '{}' -> Removing section [{}]", stripped, unwanted_section_name)
            continue

        # Check if line is at top of document and matches front page metadata
        if is_at_document_start and (
            front_page_meta_line.match(stripped)
            or ("confidential" in lower_stripped and len(stripped) < 80)
        ):
            in_front_page_block = True
            removed_front_page_lines += 1
            logger.info("Removing front page metadata line: '{}'", stripped)
            continue

        is_toc_entry = bool(toc_line_entry.match(stripped))
        is_rev_entry = bool(revision_line_entry.match(stripped))
        is_content_header = bool(content_headers.match(stripped))

        if in_unwanted_section:
            if is_content_header and not is_toc_entry and not is_rev_entry:
                logger.info("Encountered main content header: '{}' -> Exiting [{}] removal mode", stripped, unwanted_section_name)
                in_unwanted_section = False
                in_front_page_block = False
                is_at_document_start = False
            else:
                if unwanted_section_name == "Company Front Page":
                    removed_front_page_lines += 1
                elif unwanted_section_name == "Table of Contents":
                    removed_toc_lines += 1
                elif unwanted_section_name == "Revision Sheet":
                    removed_revision_lines += 1
                elif unwanted_section_name == "Acknowledgement Sheet":
                    removed_acknowledgement_lines += 1

                logger.info("Removing line inside section [{}]: '{}'", unwanted_section_name, stripped)
                continue

        if in_front_page_block and is_at_document_start:
            if is_content_header:
                in_front_page_block = False
                is_at_document_start = False
            else:
                removed_front_page_lines += 1
                logger.info("Removing front page block line: '{}'", stripped)
                continue

        # If line standalone matches TOC dot/page number pattern, skip it
        if is_toc_entry:
            removed_toc_lines += 1
            logger.info("Removing standalone TOC line entry: '{}'", stripped)
            continue

        # If line standalone matches revision entry or date pattern, skip it
        if is_rev_entry:
            removed_revision_lines += 1
            logger.info("Removing standalone revision entry/date line: '{}'", stripped)
            continue

        # If line is valid content line
        is_at_document_start = False
        cleaned_lines.append(line)

    result = "\n".join(cleaned_lines)
    result = re.sub(r"\n{3,}", "\n\n", result).strip()

    logger.info("Completed removal process. Original length: {} chars | Cleaned length: {} chars", len(text), len(result))
    logger.info("=== Cleaned Document Data ===")
    logger.info(result)
    logger.info("removal process is done")
    logger.info("Section Removal Summary -> Headers/Footers: {} lines | Front Page: {} lines | Table of Contents: {} lines | Revision Sheet: {} lines | Acknowledgement Sheet: {} lines",
                removed_header_footer_count, removed_front_page_lines, removed_toc_lines, removed_revision_lines, removed_acknowledgement_lines)

    return result