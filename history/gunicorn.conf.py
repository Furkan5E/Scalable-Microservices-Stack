bind = '0.0.0.0:5000'
workers = 2
# Threaded workers give 16 request slots, more than the 12 the web tier can open at once
# (6 pods x 2 workers at the autoscaler's maximum). During a Postgres outage every /visits call
# waits out its connect timeout, and with plain sync workers that starved /health and got
# the pod restarted by its liveness probe.
threads = 8


def on_starting(server):
    """Creates the table once in the master process, before workers fork and before the port is bound.

    Blocks until Postgres is reachable, so the readiness probe on /health reports
    not-ready until the dependency is live (replaces the old `if __name__ == '__main__'` startup).
    """
    from service import init_db
    init_db()
