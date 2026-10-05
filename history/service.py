from flask import Flask, jsonify, request
from datetime import datetime
import psycopg2
import time
import os

app = Flask(__name__)

DB_HOST = 'db'
DB_NAME = 'postgres'

DB_USER = os.environ.get('POSTGRES_USER', 'postgres')
DB_PASS = os.environ.get('POSTGRES_PASSWORD', 'password')

MAX_HOSTNAME_LENGTH = 50

STARTUP_DB_RETRIES = 5
DB_CONNECT_TIMEOUT = 2

def get_db_connection(retries=0):
    """Connects to Postgres, failing fast by default.

    Requests use the default so a database outage frees the worker straight away instead of
    holding it past the web service's timeout. Only startup passes retries, in case the DB is still booting.
    """
    while True:
        try:
            conn = psycopg2.connect(
                host=DB_HOST,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASS,
                connect_timeout=DB_CONNECT_TIMEOUT
            )
            return conn
        except psycopg2.OperationalError as e:
            if retries == 0:
                raise e
            retries -= 1
            time.sleep(2)

def init_db():
    """Creates the history table if it doesn't exist."""
    conn = get_db_connection(retries=STARTUP_DB_RETRIES)
    try:
        cur = conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS visit_history (
                id SERIAL PRIMARY KEY,
                hostname VARCHAR(50),
                visit_time TIMESTAMP
            );
        ''')
        conn.commit()
        cur.close()
    finally:
        conn.close()

@app.route('/visits', methods=['POST'])
def record_visit():
    """Records a single visit reported by the web service."""
    data = request.get_json(silent=True) or {}
    hostname = data.get('hostname')
    timestamp = data.get('timestamp')

    if not isinstance(hostname, str) or not hostname:
        return jsonify({'error': 'hostname is required and must be a non-empty string'}), 400
    if len(hostname) > MAX_HOSTNAME_LENGTH:
        return jsonify({'error': f'hostname must be {MAX_HOSTNAME_LENGTH} characters or fewer'}), 400
    if not isinstance(timestamp, str) or not timestamp:
        return jsonify({'error': 'timestamp is required and must be a non-empty string'}), 400
    try:
        datetime.fromisoformat(timestamp)
    except ValueError:
        return jsonify({'error': 'timestamp must be an ISO 8601 string'}), 400

    # Close the connection even if the insert fails, so errors don't leak connections
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            'INSERT INTO visit_history (hostname, visit_time) VALUES (%s, %s)',
            (hostname, timestamp)
        )
        conn.commit()
        cur.close()
    finally:
        conn.close()
    return jsonify({'status': 'recorded'}), 201

@app.route('/visits')
def list_visits():
    """Returns the last 10 visits stored in Postgres."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute('SELECT hostname, visit_time FROM visit_history ORDER BY visit_time DESC LIMIT 10;')
        rows = cur.fetchall()
        cur.close()
    finally:
        conn.close()

    visit_list = [
        {'hostname': r[0], 'timestamp': r[1].strftime('%Y-%m-%d %H:%M:%S')}
        for r in rows
    ]
    return jsonify(visit_list)

@app.route('/health')
def health():
    return jsonify({'status': 'ok'}), 200

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)
