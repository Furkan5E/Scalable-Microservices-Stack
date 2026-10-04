import json

import redis
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
    mock_redis.delete.assert_called_once_with('history:latest')


def test_index_reports_history_service_unavailable(client, mocker):
    """Test that / degrades gracefully when the history service can't be reached."""
    mock_redis = mocker.MagicMock()
    mock_redis.incr.return_value = 1
    mocker.patch('app.get_redis', return_value=mock_redis)
    mocker.patch('app.requests.post', side_effect=requests.RequestException('boom'))

    response = client.get('/')
    assert response.status_code == 200
    assert response.json['db_status'] == 'History service unavailable'
    mock_redis.delete.assert_not_called()


def test_index_still_serves_when_redis_unavailable(client, mocker):
    """Test that / records the visit and returns no hit count when Redis is down."""
    mock_redis = mocker.MagicMock()
    mock_redis.incr.side_effect = redis.RedisError('boom')
    mock_redis.delete.side_effect = redis.RedisError('boom')
    mocker.patch('app.get_redis', return_value=mock_redis)

    mock_post = mocker.patch('app.requests.post')
    mock_post.return_value.raise_for_status.return_value = None

    response = client.get('/')
    assert response.status_code == 200
    assert response.json['redis_visits'] is None
    assert response.json['db_status'] == 'Recorded in Postgres'
    mock_post.assert_called_once()


def test_history_cache_miss_fetches_and_caches(client, mocker):
    """Test that /history asks the history service on a cache miss and stores the result with a TTL."""
    mock_redis = mocker.MagicMock()
    mock_redis.get.return_value = None
    mocker.patch('app.get_redis', return_value=mock_redis)

    visits = [{'hostname': 'test_host', 'timestamp': '2026-08-21 21:00:00'}]
    mock_response = mocker.MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = visits
    mocker.patch('app.requests.get', return_value=mock_response)

    response = client.get('/history')
    assert response.status_code == 200
    assert response.json == visits
    assert response.headers['X-Cache'] == 'MISS'
    mock_redis.setex.assert_called_once_with('history:latest', 30, json.dumps(visits))


def test_history_cache_hit_skips_history_service(client, mocker):
    """Test that /history serves the cached value without calling the history service."""
    visits = [{'hostname': 'cached_host', 'timestamp': '2026-08-21 21:00:00'}]
    mock_redis = mocker.MagicMock()
    mock_redis.get.return_value = json.dumps(visits).encode()
    mocker.patch('app.get_redis', return_value=mock_redis)
    mock_get = mocker.patch('app.requests.get')

    response = client.get('/history')
    assert response.status_code == 200
    assert response.json == visits
    assert response.headers['X-Cache'] == 'HIT'
    mock_get.assert_not_called()


def test_history_falls_back_when_redis_unavailable(client, mocker):
    """Test that /history still answers from the history service when Redis is down."""
    mock_redis = mocker.MagicMock()
    mock_redis.get.side_effect = redis.RedisError('boom')
    mock_redis.setex.side_effect = redis.RedisError('boom')
    mocker.patch('app.get_redis', return_value=mock_redis)

    visits = [{'hostname': 'test_host', 'timestamp': '2026-08-21 21:00:00'}]
    mock_response = mocker.MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = visits
    mocker.patch('app.requests.get', return_value=mock_response)

    response = client.get('/history')
    assert response.status_code == 200
    assert response.json == visits


def test_history_returns_503_when_service_unavailable(client, mocker):
    """Test that /history returns 503 and caches nothing when the history service can't be reached."""
    mock_redis = mocker.MagicMock()
    mock_redis.get.return_value = None
    mocker.patch('app.get_redis', return_value=mock_redis)
    mocker.patch('app.requests.get', side_effect=requests.RequestException('boom'))

    response = client.get('/history')
    assert response.status_code == 503
    mock_redis.setex.assert_not_called()
