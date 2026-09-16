import requests
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


def test_index_records_visit_and_returns_hit_count(client, mocker):
    """Test that / increments the Redis counter and reports the visit to the history service."""
    mock_redis = mocker.MagicMock()
    mock_redis.incr.return_value = 3
    mocker.patch('app.get_redis', return_value=mock_redis)

    mock_post = mocker.patch('app.requests.post')
    mock_post.return_value.raise_for_status.return_value = None

    response = client.get('/')
    assert response.status_code == 200
    assert response.json['redis_visits'] == 3
    assert response.json['db_status'] == 'Recorded in Postgres'
    mock_post.assert_called_once()


def test_index_reports_history_service_unavailable(client, mocker):
    """Test that / degrades gracefully when the history service can't be reached."""
    mock_redis = mocker.MagicMock()
    mock_redis.incr.return_value = 1
    mocker.patch('app.get_redis', return_value=mock_redis)
    mocker.patch('app.requests.post', side_effect=requests.RequestException('boom'))

    response = client.get('/')
    assert response.status_code == 200
    assert response.json['db_status'] == 'History service unavailable'


def test_history_forwards_service_response(client, mocker):
    """Test that /history proxies the JSON returned by the history service."""
    mock_response = mocker.MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = [{'hostname': 'test_host', 'timestamp': '2026-08-21 21:00:00'}]
    mocker.patch('app.requests.get', return_value=mock_response)

    response = client.get('/history')
    assert response.status_code == 200
    assert response.json == [{'hostname': 'test_host', 'timestamp': '2026-08-21 21:00:00'}]


def test_history_returns_503_when_service_unavailable(client, mocker):
    """Test that /history returns 503 when the history service can't be reached."""
    mocker.patch('app.requests.get', side_effect=requests.RequestException('boom'))

    response = client.get('/history')
    assert response.status_code == 503
