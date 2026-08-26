# tests/test_ship_type_filter.py
import pytest
import asyncio
from pipeline.manual_filter import is_manual_allowed_for_ship_type
from pipeline.company_retrieval import company_retrieval_node

def test_is_manual_allowed_for_ship_type():
    # 1. Fallback / Empty user ship type -> Allow all
    assert is_manual_allowed_for_ship_type("Shipboard SMS Manual (Vol. II)-Oil Tanker 2016.docx", "") is True
    assert is_manual_allowed_for_ship_type("Shipboard SMS Manual (Vol. II)-Oil Tanker 2016.docx", None) is True
    
    # 2. Oil Tanker user
    assert is_manual_allowed_for_ship_type("Shipboard SMS Manual (Vol. II)-Oil Tanker 2016.docx", "Oil Tanker") is True
    assert is_manual_allowed_for_ship_type("Shipboard SMS Manual (Vol. II)-Oil Tanker 2016.docx", "oil tanker") is True
    assert is_manual_allowed_for_ship_type("Shipboard SMS Manual (Chemical)-Completed (1).docx", "Oil Tanker") is False
    assert is_manual_allowed_for_ship_type("Shipboard SMS Manual Vol.II-Container-2025.docx", "Oil Tanker") is False
    assert is_manual_allowed_for_ship_type("Shipboard SMS Manual (OSV).docx", "Oil Tanker") is False
    assert is_manual_allowed_for_ship_type("Shipboard SMS Manual (Vol. I) Except for OSVs 2016.docx", "Oil Tanker") is True
    assert is_manual_allowed_for_ship_type("COLD WORK PERMIT.docx", "Oil Tanker") is True

    # 3. Chemical Tanker user
    assert is_manual_allowed_for_ship_type("Shipboard SMS Manual (Vol. II)-Oil Tanker 2016.docx", "Chemical Tanker") is False
    assert is_manual_allowed_for_ship_type("Shipboard SMS Manual (Chemical)-Completed (1).docx", "Chemical Tanker") is True
    assert is_manual_allowed_for_ship_type("Shipboard SMS Manual Vol.II-Container-2025.docx", "Chemical Tanker") is False
    assert is_manual_allowed_for_ship_type("Shipboard SMS Manual (OSV).docx", "Chemical Tanker") is False
    assert is_manual_allowed_for_ship_type("Shipboard SMS Manual (Vol. I) Except for OSVs 2016.docx", "Chemical Tanker") is True
    assert is_manual_allowed_for_ship_type("Navigation and Mooring Manual (NMM).docx", "Chemical Tanker") is True

    # 4. Container user
    assert is_manual_allowed_for_ship_type("Shipboard SMS Manual (Vol. II)-Oil Tanker 2016.docx", "Container") is False
    assert is_manual_allowed_for_ship_type("Shipboard SMS Manual (Chemical)-Completed (1).docx", "Container") is False
    assert is_manual_allowed_for_ship_type("Shipboard SMS Manual Vol.II-Container-2025.docx", "Container") is True
    assert is_manual_allowed_for_ship_type("Shipboard SMS Manual (OSV).docx", "Container") is False
    assert is_manual_allowed_for_ship_type("Shipboard SMS Manual (Vol. I) Except for OSVs 2016.docx", "Container") is True
    assert is_manual_allowed_for_ship_type("Technical and Maintenance Manual (TMM).docx", "Container") is True

    # 5. OSV user
    assert is_manual_allowed_for_ship_type("Shipboard SMS Manual (Vol. II)-Oil Tanker 2016.docx", "OSV") is False
    assert is_manual_allowed_for_ship_type("Shipboard SMS Manual (Chemical)-Completed (1).docx", "OSV") is False
    assert is_manual_allowed_for_ship_type("Shipboard SMS Manual Vol.II-Container-2025.docx", "OSV") is False
    assert is_manual_allowed_for_ship_type("Shipboard SMS Manual (OSV).docx", "OSV") is True
    assert is_manual_allowed_for_ship_type("Shipboard SMS Manual (OSV).docx", "Offshore Support Vessel") is True
    assert is_manual_allowed_for_ship_type("Shipboard SMS Manual (Vol. I) Except for OSVs 2016.docx", "OSV") is False
    assert is_manual_allowed_for_ship_type("Emergency and Contingency Manual (ECM).docx", "OSV") is True

    # 6. LNG/LPG Carrier user (Gas carrier)
    assert is_manual_allowed_for_ship_type("Shipboard SMS Manual (Vol. II)-Oil Tanker 2016.docx", "LNG/LPG Carrier") is False
    assert is_manual_allowed_for_ship_type("Shipboard SMS Manual (Chemical)-Completed (1).docx", "LNG/LPG Carrier") is False
    assert is_manual_allowed_for_ship_type("Shipboard SMS Manual Vol.II-Container-2025.docx", "LNG/LPG Carrier") is False
    assert is_manual_allowed_for_ship_type("Shipboard SMS Manual (OSV).docx", "LNG/LPG Carrier") is False
    assert is_manual_allowed_for_ship_type("Shipboard SMS Manual (Vol. I) Except for OSVs 2016.docx", "LNG/LPG Carrier") is True
    assert is_manual_allowed_for_ship_type("Navigation and Mooring Manual (NMM).docx", "LNG/LPG Carrier") is True


def test_company_retrieval_node_filtering():
    class MockCompanyVectorStore:
        async def search_with_embeddings(self, query, k=30):
            return [
                {"company_id": "824866", "document_title": "Shipboard SMS Manual (Vol. II)-Oil Tanker 2016.docx", "content": "Oil checks"},
                {"company_id": "824866", "document_title": "Shipboard SMS Manual (Chemical)-Completed (1).docx", "content": "Chemical checks"},
                {"company_id": "824866", "document_title": "Shipboard SMS Manual Vol.II-Container-2025.docx", "content": "Container checks"},
                {"company_id": "824866", "document_title": "Shipboard SMS Manual (OSV).docx", "content": "OSV checks"},
                {"company_id": "824866", "document_title": "Shipboard SMS Manual (Vol. I) Except for OSVs 2016.docx", "content": "General Vol 1"},
                {"company_id": "824866", "document_title": "Navigation and Mooring Manual (NMM).docx", "content": "Nav checklist"},
            ]

    # Test Oil Tanker User
    state = {
        "user_profile": {"company_id": "824866", "ship_type": "Oil Tanker"},
        "standalone_query": "What are cargo procedures?",
        "company_chunks": []
    }
    
    updated = asyncio.run(company_retrieval_node(state, MockCompanyVectorStore()))
    titles = [c.get("document_title") for c in updated["company_chunks"]]
    
    assert "Shipboard SMS Manual (Vol. II)-Oil Tanker 2016.docx" in titles
    assert "Shipboard SMS Manual (Vol. I) Except for OSVs 2016.docx" in titles
    assert "Navigation and Mooring Manual (NMM).docx" in titles
    assert "Shipboard SMS Manual (Chemical)-Completed (1).docx" not in titles
    assert "Shipboard SMS Manual Vol.II-Container-2025.docx" not in titles
    assert "Shipboard SMS Manual (OSV).docx" not in titles
