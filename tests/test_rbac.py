"""
Tests for Role-Based Access Control (RBAC) at the retriever and vectorstore levels.
"""
import pytest
from langchain_core.documents import Document as LCDocument
from app.documents.vectorstore import add_documents, delete_document_chunks, similarity_search
from app.rag.retriever import RBACRetriever


@pytest.fixture(scope="module")
def setup_rbac_test_docs():
    # Use a unique doc_id to avoid clashing with other docs and for easy cleanup
    test_doc_id = 9999
    
    # Clean up before just in case
    delete_document_chunks(test_doc_id)
    
    # Create test chunks with different clearance levels and departments
    chunks = [
        LCDocument(
            page_content="The basic holiday allowance for all employees is 25 days per year.",
            metadata={
                "doc_id": test_doc_id,
                "clearance_level": 1,
                "department": "HR",
                "source": "employee_handbook.pdf"
            }
        ),
        LCDocument(
            page_content="Managers are authorized to approve expenses up to $5,000 without VP sign-off.",
            metadata={
                "doc_id": test_doc_id,
                "clearance_level": 2,
                "department": "Finance",
                "source": "manager_guidelines.pdf"
            }
        ),
        LCDocument(
            page_content="Project Mercury blueprints are highly confidential and describe the new admin control console.",
            metadata={
                "doc_id": test_doc_id,
                "clearance_level": 3,
                "department": "Engineering",
                "source": "project_mercury.pdf"
            }
        )
    ]
    
    add_documents(chunks)
    
    yield test_doc_id
    
    # Cleanup after test module finishes
    delete_document_chunks(test_doc_id)


def test_clearance_level_1_retrieval(setup_rbac_test_docs):
    """
    Employee (level 1) should only see level 1 documents.
    """
    # Query for something that could match any (holiday/approve/blueprint/company)
    results = similarity_search("company policy or project details", clearance_level=1, k=5)
    
    assert len(results) > 0
    # All results must be clearance level 1 or lower (none should be 2 or 3)
    for doc in results:
        assert doc.metadata["clearance_level"] <= 1
        assert doc.metadata["clearance_level"] != 2
        assert doc.metadata["clearance_level"] != 3


def test_clearance_level_2_retrieval(setup_rbac_test_docs):
    """
    Manager (level 2) should see level 1 and level 2 documents, but not level 3.
    """
    results = similarity_search("holiday policy or manager approval or project blueprints", clearance_level=2, k=5)
    
    assert len(results) > 0
    # All results must be clearance level 2 or lower (none should be 3)
    for doc in results:
        assert doc.metadata["clearance_level"] <= 2
        assert doc.metadata["clearance_level"] != 3


def test_clearance_level_3_retrieval(setup_rbac_test_docs):
    """
    Admin (level 3) should be able to see everything, including level 3.
    """
    results = similarity_search("project mercury blueprints admin console", clearance_level=3, k=5)
    
    assert len(results) > 0
    # We specifically queried for the level 3 document, verify we got it
    has_level_3 = any(doc.metadata["clearance_level"] == 3 for doc in results)
    assert has_level_3, "Admin should be able to retrieve level 3 documents"


def test_department_filtering(setup_rbac_test_docs):
    """
    Filtering by department should restrict results even if clearance level allows access.
    """
    # Query matches the HR document content
    results = similarity_search("holiday allowance policy", clearance_level=3, department="HR", k=5)
    
    assert len(results) > 0
    for doc in results:
        assert doc.metadata["department"] == "HR"
        assert doc.metadata["clearance_level"] <= 3


def test_rbac_retriever_wrapper(setup_rbac_test_docs):
    """
    Test the RBACRetriever LangChain integration.
    """
    retriever = RBACRetriever(clearance_level=1, department="HR")
    docs = retriever.invoke("holiday allowance")
    
    assert len(docs) > 0
    for doc in docs:
        assert doc.metadata["clearance_level"] <= 1
        assert doc.metadata["department"] == "HR"
