import asyncio
import pytest
from pipeline.company_retrieval import company_retrieval_node, is_company_match
from pipeline.company_query import company_query_node, _clean_content


class MockCompanyVectorStore:
    def __init__(self, metadatas=None):
        self.id_to_metadata = metadatas or []

    async def search_with_embeddings(self, query: str, k: int = 250):
        # Return all candidate chunks up to k
        results = []
        for idx, m in enumerate(self.id_to_metadata):
            c = dict(m)
            c["_faiss_index"] = idx
            results.append(c)
        return results[:k]


def test_scenario_1_detailed_company_procedure_expansion():
    """
    Test 1: Detailed company procedure spanning multiple chunks.
    Verifies that seed chunks are clustered, gaps are bridged,
    and backwards/forwards expansion retrieves the complete procedure sequence.
    """
    # Create 20 sequential chunks for an enclosed space entry procedure in doc 1
    doc1_chunks = []
    doc1_chunks.append({
        "document_id": 1,
        "company_id": "824866",
        "document_title": "Shipboard SMS Manual (Chemical)-Completed (1).docx",
        "doc_type": "Procedure",
        "chunk_index": 0,
        "content": "Section III.5.5 Entry into Enclosed Spaces\nOverview and definitions of enclosed and confined spaces."
    })
    for i in range(1, 15):
        doc1_chunks.append({
            "document_id": 1,
            "company_id": "824866",
            "document_title": "Shipboard SMS Manual (Chemical)-Completed (1).docx",
            "doc_type": "Procedure",
            "chunk_index": i,
            "content": f"Step {i}: Specific procedural requirements for enclosed space entry part {i}."
        })
    doc1_chunks.append({
        "document_id": 1,
        "company_id": "824866",
        "document_title": "Shipboard SMS Manual (Chemical)-Completed (1).docx",
        "doc_type": "Procedure",
        "chunk_index": 15,
        "content": "Emergency Action Plan and rescue protocols in case of unconscious entrant."
    })

    store = MockCompanyVectorStore(doc1_chunks)
    state = {
        "user_profile": {"company_id": "824866", "ship_type": "Chemical Tanker"},
        "standalone_query": "Explain enclosed space entry procedure",
    }

    updated = asyncio.run(company_retrieval_node(state, store))
    retrieved = updated["company_chunks"]

    # Verify all 16 contiguous chunks are retrieved without dropped steps
    assert len(retrieved) == 16
    assert retrieved[0]["chunk_index"] == 0
    assert "Section III.5.5 Entry into Enclosed Spaces" in retrieved[0]["content"]
    assert retrieved[-1]["chunk_index"] == 15
    assert "Emergency Action Plan" in retrieved[-1]["content"]


def test_scenario_2_table_preservation():
    """
    Test 2: Table information preservation.
    Verifies that multi-column tables with identical adjacent column values
    are not stripped or corrupted by _clean_content.
    """
    table_text = """| Equipment | Type | Numbers (Minimum) | Responsibility |
| :--- | :--- | :---: | :--- |
| Multi-gas detector | Portable | 2 sets | Chief Officer |
| HC Detector | Portable | 2 sets | Chief Officer |
| Personal monitor | Personal | 1 per entrant | Entrant |"""

    cleaned = _clean_content(table_text)
    assert "| Multi-gas detector | Portable | 2 sets | Chief Officer |" in cleaned
    assert "| HC Detector | Portable | 2 sets | Chief Officer |" in cleaned
    assert "| Personal monitor | Personal | 1 per entrant | Entrant |" in cleaned


def test_scenario_3_multiple_sections_retrieval():
    """
    Test 3: Multiple sections.
    Question requires information from both the SMS Manual and a Work Permit checklist.
    Verifies both documents/sections are retrieved and correctly prioritized.
    """
    chunks = [
        {
            "document_id": 2,
            "company_id": "824866",
            "document_title": "Form SS004 - Enclosed Space Entry Permit.docx",
            "doc_type": "Permit",
            "chunk_index": 0,
            "content": "Form SS004 Checklist:\n1. Atmosphere tested\n2. Ventilation running"
        },
        {
            "document_id": 1,
            "company_id": "824866",
            "document_title": "Shipboard SMS Manual (Chemical)-Completed (1).docx",
            "doc_type": "Procedure",
            "chunk_index": 50,
            "content": "Section III.5.5 Enclosed Space Entry governing policies and Master approval."
        }
    ]

    store = MockCompanyVectorStore(chunks)
    state = {
        "user_profile": {"company_id": "824866", "ship_type": "Chemical Tanker"},
        "standalone_query": "What are the rules and permit for enclosed space entry?",
    }

    updated = asyncio.run(company_retrieval_node(state, store))
    retrieved = updated["company_chunks"]

    assert len(retrieved) == 2
    # Verify primary SMS manual is sorted before Permit (Priority 0 < Priority 2)
    assert retrieved[0]["document_title"] == "Shipboard SMS Manual (Chemical)-Completed (1).docx"
    assert retrieved[1]["document_title"] == "Form SS004 - Enclosed Space Entry Permit.docx"


def test_scenario_4_company_isolation():
    """
    Test 4: Multi-tenant company isolation.
    Company A asks a question. Company B's documents must NEVER be included.
    """
    chunks = [
        {
            "document_id": 101,
            "company_id": "Company_A",
            "company_name": "Alpha Shipping",
            "document_title": "Shipboard SMS Manual (Chemical)-Completed (1).docx",
            "chunk_index": 0,
            "content": "Alpha Shipping confidential cargo operations."
        },
        {
            "document_id": 102,
            "company_id": "Company_B",
            "company_name": "Beta Shipping",
            "document_title": "Shipboard SMS Manual (Chemical)-Completed (1).docx",
            "chunk_index": 0,
            "content": "Beta Shipping proprietary procedures."
        }
    ]

    store = MockCompanyVectorStore(chunks)
    state = {
        "user_profile": {"company_id": "Company_A", "company_name": "Alpha Shipping", "ship_type": "Chemical Tanker"},
        "standalone_query": "Explain cargo operations",
    }

    updated = asyncio.run(company_retrieval_node(state, store))
    retrieved = updated["company_chunks"]

    assert len(retrieved) == 1
    assert retrieved[0]["company_id"] == "Company_A"
    assert "Alpha Shipping" in retrieved[0]["content"]
    assert all(c["company_id"] != "Company_B" for c in retrieved)


def test_scenario_5_ship_type_filtering():
    """
    Test 5: Ship type filtering.
    A document designated for a Chemical Tanker is not accessible to an Oil Tanker user,
    while their own Oil Tanker manual and universal permits are accessible.
    """
    chunks = [
        {
            "document_id": 1,
            "company_id": "824866",
            "document_title": "Shipboard SMS Manual (Chemical)-Completed (1).docx",
            "chunk_index": 0,
            "content": "Chemical Tanker specific procedures."
        },
        {
            "document_id": 8,
            "company_id": "824866",
            "document_title": "Shipboard SMS Manual (Vol. II)-Oil Tanker 2016.docx",
            "chunk_index": 0,
            "content": "Oil Tanker cargo operations."
        },
        {
            "document_id": 99,
            "company_id": "824866",
            "document_title": "Hot Work Permit Form.docx",
            "chunk_index": 0,
            "content": "Universal Hot Work Permit checklist."
        }
    ]

    store = MockCompanyVectorStore(chunks)
    state = {
        "user_profile": {"company_id": "824866", "ship_type": "Oil Tanker"},
        "standalone_query": "What are our procedures?",
    }

    updated = asyncio.run(company_retrieval_node(state, store))
    retrieved = updated["company_chunks"]

    # Chemical tanker doc filtered out; Oil tanker manual and Hot Work permit kept
    titles = [c["document_title"] for c in retrieved]
    assert "Shipboard SMS Manual (Chemical)-Completed (1).docx" not in titles
    assert "Shipboard SMS Manual (Vol. II)-Oil Tanker 2016.docx" in titles
    assert "Hot Work Permit Form.docx" in titles


def test_scenario_6_missing_company_information_fallback():
    """
    Test 6: Missing company information returns NO_COMPANY_DATA fallback.
    When company context does not contain the requested specific data,
    company_query_node sets company_answer=None and keeps the core knowledge answer.
    """
    class MockOpenAIService:
        async def chat(self, messages, temperature=0.0, **kwargs):
            return "NO_COMPANY_DATA"

    state = {
        "company_chunks": [
            {
                "document_id": 1,
                "document_title": "Shipboard SMS Manual.docx",
                "content": "General navigational watchkeeping."
            }
        ],
        "user_profile": {"company_name": "CMS Demo Company", "company_id": "1"},
        "standalone_query": "Explain EEDI and CII regulations",
        "node_response": {
            "content": "Standard maritime curriculum answer for EEDI and CII.",
            "sections": []
        }
    }

    updated_state = asyncio.run(company_query_node(state, MockOpenAIService()))
    assert updated_state["company_answer"] is None
    assert updated_state["node_response"]["content"] == "Standard maritime curriculum answer for EEDI and CII."


def test_scenario_7_cow_checklist_functionality():
    """
    Test 7: Existing COW functionality.
    Verifies that COW checklist queries correctly invoke the COW table renderer
    with all standard checks and formatting.
    """
    class MockOpenAIService:
        async def chat(self, messages, temperature=0.0, **kwargs):
            return """### 🏢 1. According to CMS Demo Company's Safety Management System (SMS / QMS)
**Document Title:** Shipboard SMS Manual (Vol. II)-Oil Tanker 2016.docx
**SOP Name:** Crude Oil Washing (COW) Procedures
**Section:** COW Checklist

Confirm all pre-arrival checks are performed [ ] [ ]

### 📘 2. Dolphin internal knowledge base
Dolphin course information for Crude Oil Washing.
"""

    state = {
        "company_chunks": [
            {
                "document_title": "Shipboard SMS Manual (Vol. II)-Oil Tanker 2016.docx",
                "content": "Crude Oil Washing (COW) pre-arrival checks and execution."
            }
        ],
        "user_profile": {"company_name": "CMS Demo Company"},
        "standalone_query": "Can you provide the COW checklist?",
        "node_response": {}
    }

    updated_state = asyncio.run(company_query_node(state, MockOpenAIService()))
    answer = updated_state["company_answer"]

    assert "COW Entry and Cleaning Checklist" in answer
    assert "| 1. Confirm all pre-arrival checks are performed |  |  | R | |" in answer
    assert "### 📘 2. Dolphin internal knowledge base" in answer
    assert "Dolphin course information for Crude Oil Washing." in answer
