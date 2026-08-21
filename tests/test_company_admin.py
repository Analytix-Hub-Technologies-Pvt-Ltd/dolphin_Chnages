import pytest
from fastapi.testclient import TestClient
from main import app
from models.company_model import CompanyDocumentListResponse, CompanyDocumentDeleteResponse
from services.company_services import CompanyDocumentService
from api.dependencies import get_db_pool
from unittest.mock import AsyncMock, MagicMock

# Create a TestClient
client = TestClient(app)

@pytest.fixture
def mock_db_pool():
    pool = AsyncMock()
    return pool

def override_get_db_pool():
    return AsyncMock()

app.dependency_overrides[get_db_pool] = override_get_db_pool

# We can mock the service methods directly to avoid real DB calls in unit tests
@pytest.fixture
def mock_company_service(monkeypatch):
    mock_service = AsyncMock()
    # Mock get_all_documents
    mock_service.get_all_documents.return_value = [
        {"document_id": 1, "company_id": "TEST_COMP", "document_title": "test1.pdf", "document_content": "test text", "content_length": 9, "is_active": True, "created_at": "2023-01-01T00:00:00"}
    ]
    # Mock delete_document
    mock_service.delete_document.return_value = True

    # Patch the service class in the router
    monkeypatch.setattr("api.company_router.CompanyDocumentService", lambda pool: mock_service)
    return mock_service

def test_list_company_documents(mock_company_service):
    response = client.get("/companies/documents")
    assert response.status_code == 200
    data = response.json()
    assert "documents" in data
    assert len(data["documents"]) == 1
    assert data["documents"][0]["document_id"] == 1
    assert data["documents"][0]["company_id"] == "TEST_COMP"

def test_delete_company_document_success(mock_company_service):
    response = client.delete("/companies/documents/1")
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Document deleted successfully"
    assert data["document_id"] == 1

def test_delete_company_document_not_found(monkeypatch):
    mock_service = AsyncMock()
    mock_service.delete_document.return_value = False
    monkeypatch.setattr("api.company_router.CompanyDocumentService", lambda pool: mock_service)

    response = client.delete("/companies/documents/999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
