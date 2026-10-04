# Scalable Microservices Stack

![Python](https://img.shields.io/badge/Python-3.14-blue?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-API-black?logo=flask&logoColor=white)
![uv](https://img.shields.io/badge/uv-Package%20Manager-6E56CF)
![Docker](https://img.shields.io/badge/Docker-Containerised-2496ED?logo=docker&logoColor=white)
![Kubernetes](https://img.shields.io/badge/Kubernetes-Orchestration-326CE5?logo=kubernetes&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-336791?logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-Cache-DC382D?logo=redis&logoColor=white)
![Nginx](https://img.shields.io/badge/Nginx-Proxy-009639?logo=nginx&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-blue.svg)
[![Test Suite](https://github.com/Furkan5E/scalable-microservices-stack/actions/workflows/test.yaml/badge.svg)](https://github.com/Furkan5E/scalable-microservices-stack/actions/workflows/test.yaml)

A containerised microservices architecture demonstrating service decomposition, inter-service communication, caching, persistent data storage, and strict dependency management.

## Architecture

The application is composed of two independently deployable Flask services plus supporting infrastructure:

| Service | Technology | Purpose |
|---|---|---|
| **Web API** | Flask | Public-facing gateway. Handles requests, tracks visit counts in Redis, caches history reads, and calls the History API over HTTP |
| **History API** | Flask | Internal service. Owns PostgreSQL exclusively; records and serves visit history on behalf of the Web API |
| **Reverse Proxy** | Nginx | Receives incoming traffic and forwards requests to the Web API |
| **Cache** | Redis | Holds the hit counter and caches the `/history` response for 30 seconds to reduce load on the History API and database |
| **Database** | PostgreSQL | Provides persistent relational data storage, accessed only by the History API |

The Web API never touches Postgres directly, it calls the History API's internal REST endpoints (`POST /visits`, `GET /visits`). This is the actual service boundary in the stack: two services with their own codebases, dependencies, containers, and failure modes, communicating over the network rather than sharing a database. On Kubernetes the boundary is enforced by NetworkPolicies: only web pods can reach the History API, and only History pods can reach Postgres.

```mermaid
flowchart LR
    Client(["Client"]) --> Nginx["Nginx\nReverse Proxy"]
    Nginx --> Web["Web API\n(Flask)"]
    Web --> Redis[("Redis\nhit counter + history cache")]
    Web -- "POST /visits\nGET /visits" --> History["History API\n(Flask, internal only)"]
    History --> Postgres[("PostgreSQL\nvisit_history")]
```

## Key Features
*   **Containerised:** Fully isolated services deployed using Docker Compose or Kubernetes.
*   **Horizontally Scalable:** The stateless Web API runs as 3 replicas on Kubernetes and autoscales to 6 under CPU load.
*   **Deterministic Builds:** Exact dependencies locked via `pyproject.toml` and `uv.lock`.
*   **Resilient Initialisation:** Custom health checks ensure the API waits for the database to be fully ready before booting.
*   **Read Caching:** `/history` is served from Redis using a cache-aside pattern with a 30 second TTL, invalidated whenever a new visit is recorded.
*   **Automated Testing:** Comprehensive Pytest suite utilising mocked database connections.
*   **Linting:** Ruff runs alongside the test suite in GitHub Actions.

## Installation

**1. Clone the repository and install dependencies**
```bash
git clone https://github.com/Furkan5E/scalable-microservices-stack.git
cd scalable-microservices-stack
uv sync
```
**2. Create a .env file in the root directory and add your secure credentials:**
```
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_secure_password
```
**3. Launch the Cluster**

Build and start all services in the background:
```bash
docker compose up --build -d
```
Check the running containers:
```bash
docker compose ps
```
To stop the application
```bash
docker compose down
```
## Deploy with Kubernetes
The manifests pull the Web API and History API images from GitHub Container Registry (`ghcr.io/furkan5e/scalable-microservices-web` and `ghcr.io/furkan5e/scalable-microservices-history`), which the Build Docker workflow publishes on every push to `master`. The images are public, so no local build or registry login is needed.

Copy the secrets template and set your own credentials (`k8s/secrets.yaml` is gitignored, so real credentials never get committed):
```bash
cp k8s/secrets.yaml.example k8s/secrets.yaml
# edit k8s/secrets.yaml with your own POSTGRES_PASSWORD
```
Apply the infrastructure manifests to local cluster
```bash
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/nginx-config.yaml
kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/postgres-networkpolicy.yaml
kubectl apply -f k8s/redis.yaml
kubectl apply -f k8s/history.yaml
kubectl apply -f k8s/history-networkpolicy.yaml
kubectl apply -f k8s/web.yaml
kubectl apply -f k8s/web-hpa.yaml
kubectl apply -f k8s/nginx.yaml
```
If you are using a local kind cluster, open a tunnel to the reverse proxy.
```bash
kubectl port-forward service/nginx 8080:8080
```
## Scaling
The Web API is stateless (the hit counter lives in Redis), so it scales horizontally. A HorizontalPodAutoscaler keeps a minimum of 3 web replicas and scales up to 6 when average CPU passes 70% of the request.

Each response reports the pod that served it, so repeated requests show the load being spread while the Redis counter stays shared:
```bash
for i in 1 2 3 4 5 6; do curl -s localhost:8080/; echo; done
```
```
{"db_status":"Recorded in Postgres","hostname":"web-5876c6c846-wj7q9","message":"Hello from the Scaled Full Stack!","redis_visits":10}
{"db_status":"Recorded in Postgres","hostname":"web-5876c6c846-785p5","message":"Hello from the Scaled Full Stack!","redis_visits":11}
{"db_status":"Recorded in Postgres","hostname":"web-5876c6c846-gqlfc","message":"Hello from the Scaled Full Stack!","redis_visits":12}
```
Scaling beyond the minimum needs the Kubernetes [metrics-server](https://github.com/kubernetes-sigs/metrics-server), which local clusters often do not ship with. Without it the stack still runs at 3 replicas. To watch the autoscaler react, generate load from inside the cluster:
```bash
kubectl run load --image=busybox:1.36 --restart=Never -- sh -c 'for j in 1 2 3 4 5 6 7 8; do (while true; do wget -q -O /dev/null http://web:5000/health; done) & done; sleep 150'
kubectl get hpa web --watch
kubectl delete pod load
```

## API Endpoints

### Web API (public, via Nginx)
`GET /` - Root endpoint. Tracks your visit count in Redis and reports the visit to the History API for persistence. Still responds if either dependency is down: `redis_visits` is `null` when Redis is unreachable, and `db_status` reports when the History API is unavailable.

`GET /health` - System diagnostic endpoint ensuring the Web API is responsive.

`GET /history` - Returns the last 10 recorded visits, from the Redis cache when available and the History API otherwise. The `X-Cache` response header reports `HIT` or `MISS`.

### History API (internal only)
`GET /health` - System diagnostic endpoint ensuring the History API is responsive.

`POST /visits` - Records a single visit `{"hostname": ..., "timestamp": ...}` in PostgreSQL.

`GET /visits` - Returns the last 10 visits stored in PostgreSQL.

## Testing
To run the automated test suite locally using uv:
```bash
uv run pytest
```
To lint the codebase:
```bash
uv run ruff check .
```
