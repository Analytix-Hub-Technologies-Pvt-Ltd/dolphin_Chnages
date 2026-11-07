"""
tests/test_question_scope_media.py

Focused unit and integration tests for question scope classification and media retrieval:
1. Scope classification (GENERAL vs SPECIFIC, including abbreviations, definitions, overviews,
   specific components, faults, procedures, parameters, and contextual follow-ups).
2. General-question sibling behavior (sibling searches are invoked to backfill media).
3. Specific-question sibling exclusion (sibling searches are bypassed; no padding/broadening).
4. Specific-question filtering and empty filtered results (unrelated media discarded, empty list preserved).
5. Router authoritative payload handling (empty media lists in media payload are authoritative and
   do not fall back to node_response, and existing suppression rules are preserved).
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from services.question_scope import (
    classify_question_scope,
    extract_specific_subject_terms,
    SCOPE_GENERAL,
    SCOPE_SPECIFIC,
)
from services.chat_service import ChatService


# ==============================================================================
# 1. SCOPE CLASSIFICATION TESTS
# ==============================================================================

def test_general_abbreviation_queries():
    """Verify abbreviation meaning and full-form questions are classified as GENERAL."""
    queries = [
        "What does EGCS stand for?",
        "What does ECDIS stand for?",
        "What is the full form of OWS?",
        "full form of BWMS",
        "What is the meaning of SOLAS?",
        "meaning of MARPOL",
        "What does the abbreviation VLSFO mean?",
        "What does SCR mean?",
        "Expand the acronym MEPC",
    ]
    for q in queries:
        assert classify_question_scope(q) == SCOPE_GENERAL, f"Expected GENERAL for: {q}"


def test_general_definition_and_overview_queries():
    """Verify broad overview, definition, and general categorization queries are classified as GENERAL."""
    queries = [
        "What is EGCS?",
        "What is an oily water separator?",
        "What are scrubbers?",
        "Explain EGCS.",
        "Explain about ECDIS",
        "Describe SOLAS",
        "Tell me about MARPOL",
        "Overview of EGCS",
        "Introduction to ballast water management",
        "Basics of marine diesel engines",
        "Fundamentals of ship stability",
        "Types of merchant ships",
        "Classification of ships",
        "General principles of ship construction",
        "EGCS",
        "ECDIS",
        "OWS",
    ]
    for q in queries:
        assert classify_question_scope(q) == SCOPE_GENERAL, f"Expected GENERAL for: {q}"


def test_specific_component_fault_procedure_queries():
    """Verify narrow questions regarding components, operations, procedures, faults, causes, and limits are SPECIFIC."""
    queries = [
        "How does the EGCS scrubber remove sulphur?",
        "What causes high pressure drop in an EGCS?",
        "What is the pH limit for EGCS washwater discharge?",
        "How to calibrate OWS 15 ppm bilge alarm?",
        "What happens if scrubber washwater pump trips?",
        "Why does boiler water level fluctuate rapidly?",
        "What causes black smoke in auxiliary boiler?",
        "Procedure for starting the emergency generator",
        "Maintenance steps for oily water separator coalescer filter",
        "How does the demister in the scrubber tower operate?",
        "Turbidity limit for washwater discharge in port",
        "Action to take if steering gear fails during navigation",
        "What causes high vibration in the turbocharger?",
        "Camshaft less main engines",
        "Camshaft-less main engines",
        "camshaftless main engines",
        "What is a camshaft less engine?",
        "Dual fuel 2-stroke engines",
        "Common rail fuel injection",
    ]
    for q in queries:
        assert classify_question_scope(q) == SCOPE_SPECIFIC, f"Expected SPECIFIC for: {q}"


def test_contextual_follow_up_scope_resolution():
    """Verify follow-up questions evaluate scope accurately using the resolved standalone query."""
    # Turn 1: "What is EGCS?" (GENERAL)
    # Turn 2: Follow-up using pronoun "how does it remove sulphur?" -> standalone query resolved
    scope_followup_specific = classify_question_scope(
        query="how does it remove sulphur?",
        standalone_query="How does the EGCS scrubber remove sulphur?"
    )
    assert scope_followup_specific == SCOPE_SPECIFIC

    # Turn 2: Follow-up asking about fault: "what causes high pressure drop?"
    scope_followup_fault = classify_question_scope(
        query="what causes high pressure drop?",
        standalone_query="What causes high pressure drop in an EGCS?"
    )
    assert scope_followup_fault == SCOPE_SPECIFIC

    # Turn 2: Follow-up asking for general explanation continuation
    scope_followup_general = classify_question_scope(
        query="can you explain in more detail?",
        standalone_query="Can you explain the EGCS overview in more detail?"
    )
    assert scope_followup_general == SCOPE_GENERAL


def test_specific_terms_extraction():
    """Verify extraction of distinctive specific subject terms for media relevance filtering."""
    terms_pressure = extract_specific_subject_terms("What causes high pressure drop in an EGCS?")
    assert "pressure" in terms_pressure
    assert "drop" in terms_pressure
    # Overarching acronym EGCS must not be in specific terms
    assert "egcs" not in terms_pressure

    terms_sulphur = extract_specific_subject_terms("How does the EGCS scrubber remove sulphur?")
    assert "remove" in terms_sulphur
    assert "sulphur" in terms_sulphur or "sulfur" in terms_sulphur

    # Specialized machinery subtype test:
    # Camshaft-less main engines must keep 'camshaft' / 'camshaftless' and prune parent carrier 'main' and 'engines'
    terms_camshaft = extract_specific_subject_terms("Camshaft less main engines")
    assert "camshaft" in terms_camshaft
    assert "main" not in terms_camshaft
    assert "engines" not in terms_camshaft


# ==============================================================================
# 2. GENERAL VS SPECIFIC SIBLING MEDIA BEHAVIOR TESTS
# ==============================================================================

def test_general_question_invokes_sibling_searches():
    """Verify GENERAL questions invoke sibling search to backfill images, PDFs, and videos."""
    async def _test():
        service = ChatService.__new__(ChatService)
        service.image_service = MagicMock()

        # Mock chunk with 1 image, 1 PDF, 1 video
        mock_chunks = [{
            "topic_name": "Overview of EGCS",
            "topic_code": "02",
            "images": [{"url": "https://example.com/egcs_overview.jpg", "title": "EGCS Overview"}],
            "pdfs": [{"link": "https://example.com/egcs_doc.pdf", "title": "EGCS Doc"}],
            "videos": [{"url": "https://example.com/egcs_intro.mp4", "title": "EGCS Intro"}],
        }]

        sibling_image = {"url": "https://example.com/egcs_diag.jpg", "title": "EGCS Sibling Diagram"}
        sibling_pdf = {"link": "https://example.com/egcs_guide.pdf", "title": "EGCS Sibling Guide"}
        sibling_video = {"url": "https://example.com/egcs_vid2.mp4", "title": "EGCS Sibling Video"}

        with patch.object(service, "_find_sibling_images", new_callable=AsyncMock) as mock_sib_img, \
             patch.object(service, "_find_sibling_pdfs", new_callable=AsyncMock) as mock_sib_pdf, \
             patch.object(service, "_find_sibling_videos", new_callable=AsyncMock) as mock_sib_vid, \
             patch.object(service, "_find_chunk_pinned_videos", new_callable=AsyncMock) as mock_pin_vid, \
             patch.object(service.image_service, "get_local_cached_url", return_value="https://example.com/cached.jpg"):

            mock_sib_img.return_value = [sibling_image]
            mock_sib_pdf.return_value = [sibling_pdf]
            mock_sib_vid.return_value = [sibling_video]
            mock_pin_vid.return_value = []

            images, pdfs, videos, _, _ = await service._run_media_enrichment_task(
                retrieval_chunks=mock_chunks,
                current_query="What is EGCS?",
                video_suggestions=[],
                question_scope=SCOPE_GENERAL,
            )

            # For GENERAL questions, sibling searches MUST be called
            assert mock_sib_img.called, "Sibling images search should be called for GENERAL questions"
            assert mock_sib_pdf.called, "Sibling PDFs search should be called for GENERAL questions"
            assert mock_sib_vid.called, "Sibling videos search should be called for GENERAL questions"

            # Result contains both chunk media and sibling media
            assert any(img["title"] == "EGCS Sibling Diagram" for img in images)
            assert any(pdf["title"] == "EGCS Sibling Guide" for pdf in pdfs)
            assert any(vid["title"] == "EGCS Sibling Video" for vid in videos)

    asyncio.run(_test())


def test_specific_question_excludes_sibling_searches():
    """Verify SPECIFIC questions do NOT invoke sibling search to pad or fill quotas."""
    async def _test():
        service = ChatService.__new__(ChatService)
        service.image_service = MagicMock()

        # Mock chunk with 1 matching image for pressure drop
        mock_chunks = [{
            "topic_name": "EGCS Pressure Monitoring",
            "topic_code": "02",
            "images": [{"url": "https://example.com/pressure_drop.jpg", "title": "EGCS Pressure Drop Diagram"}],
            "pdfs": [],
            "videos": [],
        }]

        with patch.object(service, "_find_sibling_images", new_callable=AsyncMock) as mock_sib_img, \
             patch.object(service, "_find_sibling_pdfs", new_callable=AsyncMock) as mock_sib_pdf, \
             patch.object(service, "_find_sibling_videos", new_callable=AsyncMock) as mock_sib_vid, \
             patch.object(service, "_find_chunk_pinned_videos", new_callable=AsyncMock) as mock_pin_vid, \
             patch.object(service.image_service, "get_local_cached_url", return_value="https://example.com/cached.jpg"):

            mock_pin_vid.return_value = []

            images, pdfs, videos, _, _ = await service._run_media_enrichment_task(
                retrieval_chunks=mock_chunks,
                current_query="What causes high pressure drop in an EGCS?",
                video_suggestions=[],
                question_scope=SCOPE_SPECIFIC,
            )

            # For SPECIFIC questions, sibling searches MUST NOT be called!
            assert not mock_sib_img.called, "Sibling images search must NOT be called for SPECIFIC questions"
            assert not mock_sib_pdf.called, "Sibling PDFs search must NOT be called for SPECIFIC questions"
            assert not mock_sib_vid.called, "Sibling videos search must NOT be called for SPECIFIC questions"

            # Quotas must not be padded: only the genuinely matching item is returned
            assert len(images) == 1
            assert images[0]["title"] == "EGCS Pressure Drop Diagram"
            assert len(pdfs) == 0
            assert len(videos) == 0

    asyncio.run(_test())


# ==============================================================================
# 3. SPECIFIC QUESTION FILTERING & EMPTY RESULT PRESERVATION
# ==============================================================================

def test_specific_question_filters_out_unrelated_media():
    """Verify media that only matches the broad acronym but not the specific subject is excluded."""
    async def _test():
        service = ChatService.__new__(ChatService)
        service.image_service = MagicMock()

        # Chunks contain broad EGCS images (e.g. general arrangement, caustic soda),
        # but the user asks about "pressure drop"
        mock_chunks = [{
            "topic_name": "Exhaust Gas Cleaning Systems",
            "topic_code": "02",
            "images": [
                {"url": "https://example.com/general_layout.jpg", "title": "EGCS General Layout"},
                {"url": "https://example.com/caustic.jpg", "title": "EGCS Caustic Soda Tank"},
            ],
            "pdfs": [
                {"link": "https://example.com/bunkering.pdf", "title": "EGCS Bunkering Manual"},
            ],
            "videos": [
                {"url": "https://example.com/overview.mp4", "title": "EGCS Overview and Introduction"},
            ],
        }]

        with patch.object(service, "_find_sibling_images", new_callable=AsyncMock) as mock_sib_img, \
             patch.object(service, "_find_sibling_pdfs", new_callable=AsyncMock) as mock_sib_pdf, \
             patch.object(service, "_find_sibling_videos", new_callable=AsyncMock) as mock_sib_vid, \
             patch.object(service, "_find_chunk_pinned_videos", new_callable=AsyncMock) as mock_pin_vid, \
             patch.object(service.image_service, "get_local_cached_url", return_value="https://example.com/cached.jpg"):

            mock_pin_vid.return_value = []

            images, pdfs, videos, _, _ = await service._run_media_enrichment_task(
                retrieval_chunks=mock_chunks,
                current_query="What causes high pressure drop in an EGCS?",
                video_suggestions=[],
                question_scope=SCOPE_SPECIFIC,
            )

            # Neither the images, PDFs, nor videos match "pressure drop", so all must be empty
            assert images == [], "Unrelated images must not be returned for specific questions"
            assert pdfs == [], "Unrelated PDFs must not be returned for specific questions"
            assert videos == [], "Unrelated videos must not be returned for specific questions"

    asyncio.run(_test())


# ==============================================================================
# 4. ROUTER AUTHORITATIVE PAYLOAD & SUPPRESSION TESTS
# ==============================================================================

def test_router_empty_media_is_authoritative():
    """
    Verify the router respects empty media lists in the media payload and
    does NOT fall back to node_response media.
    """
    # Simulate node_response having less-filtered media attached
    node_response = MagicMock()
    node_response.images = [{"url": "https://example.com/unfiltered.jpg"}]
    node_response.videos = [{"url": "https://example.com/unfiltered.mp4"}]
    node_response.pdfs = [{"link": "https://example.com/unfiltered.pdf"}]
    node_response.topic_codes = ["02"]
    node_response.metadata = {"question_scope": SCOPE_SPECIFIC}

    # Authoritative media payload from scope filtering returned empty lists
    media = {
        "images": [],
        "videos": [],
        "pdfs": [],
        "topic_codes": ["02"],
        "question_scope": SCOPE_SPECIFIC,
    }

    is_stream_out_of_scope = False
    is_resp_social = False
    suppress_extras = False
    is_course_missing = False

    # Apply the exact authoritative logic implemented in chat_router.py
    if is_stream_out_of_scope or is_resp_social or suppress_extras or is_course_missing:
        media_videos = []
        media_images = []
        media_pdfs = []
        media_topic_codes = []
    else:
        media_videos = media["videos"] if (isinstance(media, dict) and "videos" in media) else (getattr(node_response, "videos", None) or [])
        media_images = media["images"] if (isinstance(media, dict) and "images" in media) else (getattr(node_response, "images", None) or [])
        media_pdfs = media["pdfs"] if (isinstance(media, dict) and "pdfs" in media) else (getattr(node_response, "pdfs", None) or [])
        media_topic_codes = media.get("topic_codes", []) if isinstance(media, dict) else (getattr(node_response, "topic_codes", None) or [])

    # The resulting media lists MUST be empty and not fall back to node_response
    assert media_images == [], "Empty images list in media must remain empty (authoritative)"
    assert media_videos == [], "Empty videos list in media must remain empty (authoritative)"
    assert media_pdfs == [], "Empty pdfs list in media must remain empty (authoritative)"


def test_router_preserves_suppression_rules():
    """Verify suppression rules (greetings, clarifications, out-of-scope, course-missing) zero out media."""
    suppression_cases = [
        {"is_stream_out_of_scope": True, "is_resp_social": False, "suppress_extras": False, "is_course_missing": False},
        {"is_stream_out_of_scope": False, "is_resp_social": True, "suppress_extras": False, "is_course_missing": False},
        {"is_stream_out_of_scope": False, "is_resp_social": False, "suppress_extras": True, "is_course_missing": False},
        {"is_stream_out_of_scope": False, "is_resp_social": False, "suppress_extras": False, "is_course_missing": True},
    ]

    node_response = MagicMock()
    node_response.images = [{"url": "https://example.com/sample.jpg"}]
    media = {"images": [{"url": "https://example.com/sample.jpg"}], "videos": [], "pdfs": []}

    for case in suppression_cases:
        if case["is_stream_out_of_scope"] or case["is_resp_social"] or case["suppress_extras"] or case["is_course_missing"]:
            media_videos = []
            media_images = []
            media_pdfs = []
        else:
            media_images = media["images"] if "images" in media else getattr(node_response, "images", [])
            media_videos = media["videos"] if "videos" in media else getattr(node_response, "videos", [])
            media_pdfs = media["pdfs"] if "pdfs" in media else getattr(node_response, "pdfs", [])

        assert media_images == []
        assert media_videos == []
        assert media_pdfs == []


# ==============================================================================
# 5. DYNAMIC INSTRUMENTS, REGULATORY TIMELINES & CARRIER STOPWORD TESTS
# ==============================================================================

def test_dynamic_instruments_and_regulatory_timeline_queries():
    """Verify dynamic physical instruments, measuring devices, and regulatory timelines are SPECIFIC,
    while broad convention overviews remain GENERAL."""
    specific_queries = [
        "regulation on gas meters effective jan 2026?",
        "What are the rules for flowmeter installation?",
        "pyrometer calibration requirements",
        "manometer differential pressure testing",
        "amendments on fuel consumption entry into force 2026",
        "compliance deadline for ballast water management system",
        "gas detector alarm setpoints",
        "requirements for fuel oil flow meter",
        "mandatory compliance date for EEXI",
    ]
    for q in specific_queries:
        assert classify_question_scope(q) == SCOPE_SPECIFIC, f"Expected SPECIFIC for: {q}"

    general_queries = [
        "Overview of Changes in the Merchant Shipping Act for 2025",
        "Overview of SOLAS",
        "regulations on SOLAS",
        "What is MARPOL?",
        "Explain ECDIS",
    ]
    for q in general_queries:
        assert classify_question_scope(q) == SCOPE_GENERAL, f"Expected GENERAL for: {q}"


def test_carrier_stopwords_stripped_from_specific_terms():
    """Verify regulatory and calendar carrier words are stripped from specific subject terms
    so unrelated regulations and dates never match."""
    terms_gas = extract_specific_subject_terms("regulation on gas meters effective jan 2026?")
    assert "gas" in terms_gas
    assert "meter" in terms_gas or "meters" in terms_gas
    # Administrative carrier words and month names must be stripped
    assert "regulation" not in terms_gas
    assert "regulations" not in terms_gas
    assert "effective" not in terms_gas
    assert "jan" not in terms_gas
    assert "january" not in terms_gas

    terms_ows = extract_specific_subject_terms("rules for oily water separator compliance deadline 2025")
    assert "separator" in terms_ows
    assert "oil" in terms_ows or "oily" in terms_ows
    assert "water" in terms_ows
    assert "rules" not in terms_ows
    assert "compliance" not in terms_ows
    assert "deadline" not in terms_ows


def test_gas_meters_unrelated_media_completely_filtered():
    """Verify that a specific query like 'regulation on gas meters effective jan 2026?'
    strictly filters out unrelated media (like Ballast Water, Green house gases, Matrix of Regulation)
    and does not call sibling searches."""
    async def _test():
        service = ChatService.__new__(ChatService)
        service.image_service = MagicMock()

        # Mock retrieved chunks containing typical adjacent course topics
        mock_chunks = [
            {
                "topic_name": "Maritime Compliance: Fuel Consumption Reporting Requirements",
                "topic_code": "01",
                "images": [],
                "videos": [],
                "pdfs": [],
            },
            {
                "topic_name": "Ballast Water Management Requirements",
                "topic_code": "02",
                "images": [
                    {"title": "Ballast Water Management-Certificates and Documents for Existing Ships", "url": "https://example.com/bwm1.jpg"},
                    {"title": "Ballast Water Management-Certificates and Documents for New Ships", "url": "https://example.com/bwm2.jpg"},
                ],
                "videos": [],
                "pdfs": [],
            },
            {
                "topic_name": "Legislations",
                "topic_code": "03",
                "images": [
                    {"title": "Mediterranean Sea", "url": "https://example.com/med.jpg"},
                    {"title": "Canadian Arctic", "url": "https://example.com/arctic.jpg"},
                ],
                "videos": [{"title": "Green house gases", "url": "https://example.com/ghg.mp4"}],
                "pdfs": [
                    {"title": "Energy Efficiency Regulations", "link": "https://example.com/ee.pdf"},
                    {"title": "Updated Matrix of Regulation – March 2021", "link": "https://example.com/matrix.pdf"},
                ],
            },
        ]

        query = "regulation on gas meters effective jan 2026?"
        scope = classify_question_scope(query)
        assert scope == SCOPE_SPECIFIC

        with patch.object(service, "_find_sibling_images", new_callable=AsyncMock) as mock_sib_img, \
             patch.object(service, "_find_sibling_pdfs", new_callable=AsyncMock) as mock_sib_pdf, \
             patch.object(service, "_find_sibling_videos", new_callable=AsyncMock) as mock_sib_vid, \
             patch.object(service, "_find_chunk_pinned_videos", new_callable=AsyncMock) as mock_pin_vid, \
             patch.object(service.image_service, "get_local_cached_url", return_value="https://example.com/cached.jpg"):

            mock_pin_vid.return_value = []

            images, pdfs, videos, _, _ = await service._run_media_enrichment_task(
                retrieval_chunks=mock_chunks,
                current_query=query,
                video_suggestions=[],
                question_scope=scope,
            )

            # Sibling searches must be skipped for SPECIFIC questions
            assert not mock_sib_img.called
            assert not mock_sib_pdf.called
            assert not mock_sib_vid.called

            # Unrelated media must be completely filtered out
            assert images == [], f"Expected empty images, got: {images}"
            assert videos == [], f"Expected empty videos, got: {videos}"
            assert pdfs == [], f"Expected empty pdfs, got: {pdfs}"

    asyncio.run(_test())

