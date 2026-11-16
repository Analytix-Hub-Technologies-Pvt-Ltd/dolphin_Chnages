import re
import pytest
from pipeline.query import generate_subtopic_header, clean_subtopic_target_name, generate_subtopic_metadata

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

def test_generate_subtopic_metadata_concise():
    # Verify raw text forms a clean 2-line summary without repetitive boilerplate or syllabus text
    raw_content = (
        "Fire Detection and Alarms - Upper Deck and Engine Room The BS-100/4 fire detection system is a "
        "fully addressable analogue fire alarm system with computerization and analogue detectors. "
        "The system's central control unit includes a back-up battery, operating panel, and power supply. "
        "There is a repeater panel."
    )
    meta = generate_subtopic_metadata("Fire Detection System", raw_content=raw_content)
    assert meta["title"] == "Fire Detection System"
    assert len(meta["explanation"]) >= 120 and len(meta["explanation"]) <= 245
    # Crucially ensure repetitive boilerplate is absent and NEVER ends with '...'
    assert "This section outlines key regulatory guidelines" not in meta["explanation"]
    assert not meta["explanation"].endswith(("...", "…"))
    assert meta["explanation"].endswith(".")

    # Test syllabus / learning objective cleanup and zero '...'
    syllabus_raw = (
        "After going through this topic , exhaust gas cleaning ( EGC ) , also known as SOx scrubbing , has been an integral part of the "
        "solution to reduce the SOx emissions to statutory levels. Details automated trips and safety controls."
    )
    meta_syllabus = generate_subtopic_metadata("Scrubber Operation and Safety Features", raw_content=syllabus_raw)
    assert "After going through this topic" not in meta_syllabus["explanation"]
    assert not meta_syllabus["explanation"].endswith(("...", "…"))
    assert meta_syllabus["explanation"].endswith(".")
    assert len(meta_syllabus["explanation"]) >= 100

    # Test scrubber / EGCS domain branches are clean 2 lines with zero '...'
    meta_wet = generate_subtopic_metadata("Wet Scrubbing", raw_content="Wet Scrubbers Wet Scrubbing Process : The objective of the EGC Systems is to dissolve the water soluble gases.")
    assert not meta_wet["explanation"].endswith(("...", "…"))
    assert meta_wet["explanation"].endswith(".")
    assert len(meta_wet["explanation"]) >= 140

    # Test domain-specific rule is 2 lines (~180-220 chars) with zero '...'
    meta_ecdis = generate_subtopic_metadata("Comparison of ECDIS and Paper Charts", raw_content="")
    assert len(meta_ecdis["explanation"]) >= 160 and len(meta_ecdis["explanation"]) <= 240
    assert "This section outlines key regulatory guidelines" not in meta_ecdis["explanation"]
    assert not meta_ecdis["explanation"].endswith(("...", "…"))
    assert meta_ecdis["explanation"].endswith(".")
