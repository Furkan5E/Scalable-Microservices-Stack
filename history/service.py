from flask import Flask, jsonify, request
import psycopg2
import time
import os

app = Flask(__name__)

DB_HOST = 'db'
DB_NAME = 'postgres'

DB_USER = os.environ.get('POSTGRES_USER', 'postgres')
DB_PASS = os.environ.get('POSTGRES_PASSWORD', 'password')

def get_db_connection():
    """Connects to Postgres with a simple retry loop in case the DB is still booting."""
    retries = 5
    while True:
        try:
            conn = psycopg2.connect(
                host=DB_HOST,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASS
            )
            return conn
        except psycopg2.OperationalError as e:
            if retries == 0:
                raise e
            retries -= 1
            time.sleep(2)

def init_db():
    """Creates the history table if it doesn't exist."""
    conn = get_db_connection()
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
    conn.close()

@app.route('/visits', methods=['POST'])
def record_visit():
    """Records a single visit reported by the web service."""
    data = request.get_json()
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        'INSERT INTO visit_history (hostname, visit_time) VALUES (%s, %s)',
        (data['hostname'], data['timestamp'])
    )
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({'status': 'recorded'}), 201

@app.route('/visits')
def list_visits():
    """Returns the last 10 visits stored in Postgres."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT hostname, visit_time FROM visit_history ORDER BY visit_time DESC LIMIT 10;')
    rows = cur.fetchall()
    cur.close()
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
