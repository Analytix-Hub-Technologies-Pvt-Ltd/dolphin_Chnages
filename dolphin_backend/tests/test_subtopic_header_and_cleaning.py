import re
import pytest
from pipeline.query import generate_subtopic_header, clean_subtopic_target_name

def test_clean_subtopic_target_name_bullet_and_colon():
    assert clean_subtopic_target_name("• Egcs:") == "EGCS"
    assert clean_subtopic_target_name("\n • Egcs: ") == "EGCS"
    assert clean_subtopic_target_name("- ecdis:") == "ECDIS"
    assert clean_subtopic_target_name("1. SOLAS") == "SOLAS"
    assert clean_subtopic_target_name("Overview of Exhaust Gas Cleaning Systems (EGCS)") == "EGCS"
    assert clean_subtopic_target_name("") == ""
    assert clean_subtopic_target_name("   ") == ""

def test_generate_subtopic_header_formatting():
    assert generate_subtopic_header("• Egcs:") == "**Which aspect of EGCS would you like to explore?**"
    assert generate_subtopic_header("\n • Egcs: ") == "**Which aspect of EGCS would you like to explore?**"
    assert generate_subtopic_header("ECDIS") == "**Which aspect of ECDIS would you like to explore?**"
    assert generate_subtopic_header("") == "**Which aspect would you like to explore?**"
    assert generate_subtopic_header(None, query="what is OMM?") == "**Which aspect of OMM would you like to explore?**"

def test_core_definition_label_stripping():
    # Test regex patterns used in query.py
    pattern1 = r'(?im)^(?:\s*[-*#]+\s*)?(?:\*\*)?Core\s+Definition\s*(?:&|and)\s*Principle:?(?:\*\*)?:?\s*\n*'
    pattern2 = r'(?i)(?:\*\*)?Core\s+Definition\s*(?:&|and)\s*Principle:?(?:\*\*)?:?\s*'

    raw1 = "Core Definition & Principle:\nAn Exhaust Gas Cleaning System (EGCS) is designed to remove SOx."
    cleaned1 = re.sub(pattern1, '', raw1)
    assert cleaned1 == "An Exhaust Gas Cleaning System (EGCS) is designed to remove SOx."

    raw2 = "**Core Definition & Principle:** An Exhaust Gas Cleaning System (EGCS) is designed to remove SOx."
    cleaned2 = re.sub(pattern2, '', raw2).strip()
    assert cleaned2 == "An Exhaust Gas Cleaning System (EGCS) is designed to remove SOx."

    raw3 = "### Core Definition and Principle\nAn EGCS operates by..."
    cleaned3 = re.sub(pattern1, '', raw3)
    assert cleaned3 == "An EGCS operates by..."
