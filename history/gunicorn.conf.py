bind = '0.0.0.0:5000'
workers = 2


def on_starting(server):
    """Creates the table once in the master process, before workers fork and before the port is bound.

    Blocks until Postgres is reachable, so the readiness probe on /health reports
    not-ready until the dependency is live (replaces the old `if __name__ == '__main__'` startup).
    """
    from service import init_db
    init_db()
