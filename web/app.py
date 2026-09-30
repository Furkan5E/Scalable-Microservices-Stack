from flask import Flask, jsonify
import redis
import socket
import requests
from datetime import datetime
import json
import os

app = Flask(__name__)

REDIS_HOST = 'redis'
HISTORY_SERVICE_URL = os.environ.get('HISTORY_SERVICE_URL', 'http://history:5000')

HISTORY_CACHE_KEY = 'history:latest'
HISTORY_CACHE_TTL = 30

def get_redis():
    return redis.Redis(host=REDIS_HOST, port=6379)

@app.route('/')
def index():
    # 1. Increment Redis counter
    cache = get_redis()
    hits = cache.incr('hits')

    # 2. Get local info
    hostname = socket.gethostname()
    now = datetime.now().isoformat()

    # 3. Ask the history service to record the visit in Postgres
    db_status = 'Recorded in Postgres'
    try:
        response = requests.post(
            f'{HISTORY_SERVICE_URL}/visits',
            json={'hostname': hostname, 'timestamp': now},
            timeout=3
        )
        response.raise_for_status()
        # 4. Drop the cached history so the new visit shows up straight away
        cache.delete(HISTORY_CACHE_KEY)
    except requests.RequestException:
        db_status = 'History service unavailable'

    return jsonify({
        'message': 'Hello from the Scaled Full Stack!',
        'hostname': hostname,
        'redis_visits': int(hits),
        'db_status': db_status
    })

@app.route('/history')
def history():
    """Returns the last 10 visits, from the Redis cache when present and the history service otherwise."""
    cache = get_redis()

    # 1. Try the cache first; a Redis failure is treated as a miss
    try:
        cached = cache.get(HISTORY_CACHE_KEY)
    except redis.RedisError:
        cached = None
    if cached is not None:
        response = app.response_class(cached, mimetype='application/json')
        response.headers['X-Cache'] = 'HIT'
        return response

    # 2. Cache miss: ask the history service
    try:
        upstream = requests.get(f'{HISTORY_SERVICE_URL}/visits', timeout=3)
        upstream.raise_for_status()
        visits = upstream.json()
    except requests.RequestException:
        return jsonify({'error': 'History service unavailable'}), 503

    # 3. Store the result with a TTL so stale entries expire on their own
    try:
        cache.setex(HISTORY_CACHE_KEY, HISTORY_CACHE_TTL, json.dumps(visits))
    except redis.RedisError:
        pass

    response = jsonify(visits)
    response.headers['X-Cache'] = 'MISS'
    return response

@app.route('/health')
def health():
    return jsonify({'status': 'ok'}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
