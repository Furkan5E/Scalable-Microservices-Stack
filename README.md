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

A containerised, production ready microservices architecture demonstrating modern deployment practices, caching, persistent data storage, and strict dependency management.

## Architecture

The application is composed of four core services:

| Service | Technology | Purpose |
|---|---|---|
| **Web API** | Flask | Handles application logic and API requests |
| **Reverse Proxy** | Nginx | Receives incoming traffic and forwards requests to the API |
| **Cache** | Redis | Stores frequently accessed data in memory to reduce database load |
| **Database** | PostgreSQL | Provides persistent relational data storage |

## Key Features
*   **Containerised:** Fully isolated services deployed using Docker Compose or Kubernetes.
*   **Deterministic Builds:** Exact dependencies locked via `pyproject.toml` and `uv.lock`.
*   **Resilient Initialisation:** Custom health checks ensure the API waits for the database to be fully ready before booting.
*   **Automated Testing:** Comprehensive Pytest suite utilising mocked database connections.

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
Apply the infrastructure manifests to local cluster
```bash
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/nginx-config.yaml
kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/redis.yaml
kubectl apply -f k8s/web.yaml
kubectl apply -f k8s/nginx.yaml
```
If you are using a local kind cluster, open a tunnel to the reverse proxy.
```bash
kubectl port-forward service/nginx 8080:8080
```
## API Endpoints
`GET /` - Root endpoint. Logs your hostname and timestamp to PostgreSQL and tracks your visit count in Redis.

`GET /health` - System diagnostic endpoint ensuring the API is responsive.

`GET /history` - Retrieves the full JSON log of all recorded visits from the database.

## Testing
To run the automated test suite locally using uv:
```bash
uv run pytest
```
