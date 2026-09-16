from flask import Flask, jsonify
import redis
import socket
import requests
from datetime import datetime
import os

app = Flask(__name__)

REDIS_HOST = 'redis'
HISTORY_SERVICE_URL = os.environ.get('HISTORY_SERVICE_URL', 'http://history:5000')

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
    """Proxies the last 10 visits from the history service."""
    try:
        response = requests.get(f'{HISTORY_SERVICE_URL}/visits', timeout=3)
        response.raise_for_status()
        return jsonify(response.json())
    except requests.RequestException:
        return jsonify({'error': 'History service unavailable'}), 503

@app.route('/health')
def health():
    return jsonify({'status': 'ok'}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
