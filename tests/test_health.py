import os
import sys
from pathlib import Path
from unittest import mock
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

@mock.patch("sentence_transformers.SentenceTransformer")
def test_health_endpoint(mock_st):
    import main
    client = TestClient(main.app)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    for key in ["status", "embedder", "qdrant_configured", "collection"]:
        assert key in data
    expected_status = os.getenv("STATUS_MESSAGE", "ChainDocs API is alive!")
    assert data["status"] == expected_status
