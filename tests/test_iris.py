"""IRIS v7 Tests"""
import pytest
import json
from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_health(client):
    """Test health endpoint"""
    response = client.get('/api/health')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['status'] == 'online'
    assert data['name'] == 'IRIS'

def test_auth_required(client):
    """Test auth required for protected routes"""
    response = client.get('/api/documents')
    assert response.status_code == 401

def test_consciousness_state(client):
    """Test consciousness endpoint"""
    # Would need auth token in real test
    pass

def test_self_analyze():
    """Test self-improvement analysis"""
    from modules.self_improve import self_improvement
    result = self_improvement.analyze_self()
    assert 'total_files' in result
    assert 'total_issues' in result
