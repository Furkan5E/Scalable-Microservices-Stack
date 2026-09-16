from datetime import datetime

import pytest
from service import app


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_health_endpoint(client):
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json == {'status': 'ok'}


def test_list_visits_format(client, mocker):
    """Test that /visits returns the last visits formatted from Postgres rows."""
    mock_cursor = mocker.MagicMock()
    mock_cursor.fetchall.return_value = [('test_host', datetime(2026, 8, 21, 21, 0, 0))]
    mock_conn = mocker.MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mocker.patch('service.get_db_connection', return_value=mock_conn)

    response = client.get('/visits')
    assert response.status_code == 200
    assert response.json == [{'hostname': 'test_host', 'timestamp': '2026-08-21 21:00:00'}]


def test_record_visit(client, mocker):
    """Test that POST /visits inserts a row and returns 201."""
    mock_cursor = mocker.MagicMock()
    mock_conn = mocker.MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mocker.patch('service.get_db_connection', return_value=mock_conn)

    response = client.post('/visits', json={'hostname': 'test_host', 'timestamp': '2026-08-21T21:00:00'})
    assert response.status_code == 201
    mock_cursor.execute.assert_called_once()
