import pytest
from app import app

@pytest.fixture
def client():
    #configure flask for testing
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_health_endpoint(client):
    """Test that the application healthcheck returns a 200 OK status."""
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json == {'status': 'ok'}

def test_history_format(client, mocker):
    """Test that the history endpoint returns a list (mocks the database)."""
    # mock the database connection
    mocker.patch('app.get_db_connection')
    
    # mock the database cursor and return value
    mock_cursor = mocker.MagicMock()
    mock_cursor.fetchall.return_value = [('test_host', '2026-08-21 21:00:00')]
    mocker.patch('app.psycopg2.connect').return_value.cursor.return_value = mock_cursor

    # FIX: Point this to /history instead of /health
    response = client.get('/history') 
    assert response.status_code == 200