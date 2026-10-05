#!/usr/bin/env bash
# End-to-end smoke test for a deployed stack. Assumes kubectl points at a cluster
# where the manifests in k8s/ have already been applied.
set -euo pipefail

BASE_URL=http://localhost:8080

fail() {
    echo "FAIL: $1"
    exit 1
}

echo 'Waiting for all deployments to become available...'
kubectl wait --for=condition=available deployment --all --timeout=300s

echo 'Waiting for the autoscaler to bring web up to 3 replicas...'
ready=0
for _ in $(seq 1 36); do
    ready=$(kubectl get deployment web -o jsonpath='{.status.readyReplicas}')
    [ "${ready:-0}" -ge 3 ] && break
    sleep 5
done
[ "${ready:-0}" -ge 3 ] || fail "web has ${ready:-0} ready replicas, expected at least 3"

kubectl port-forward service/nginx 8080:8080 >/dev/null 2>&1 &
PORT_FORWARD_PID=$!
trap 'kill $PORT_FORWARD_PID 2>/dev/null || true' EXIT

echo 'Checking /health through nginx...'
healthy=no
for _ in $(seq 1 20); do
    if curl -fs "$BASE_URL/health" | grep -q '"status":"ok"'; then
        healthy=yes
        break
    fi
    sleep 1
done
[ "$healthy" = yes ] || fail '/health did not return ok'

echo 'Checking / records a visit in Redis and Postgres...'
body=$(curl -fs "$BASE_URL/")
echo "$body" | grep -q '"db_status":"Recorded in Postgres"' || fail "visit was not recorded: $body"
echo "$body" | grep -Eq '"redis_visits":[0-9]+' || fail "no Redis hit count: $body"

echo 'Checking /history is served from the History API, then from the cache...'
first=$(curl -fs -D - "$BASE_URL/history")
echo "$first" | grep -qi 'x-cache: MISS' || fail 'first /history request was not a cache miss'
echo "$first" | grep -q '"hostname":"web-' || fail 'history does not contain the recorded visit'
curl -fs -D - -o /dev/null "$BASE_URL/history" | grep -qi 'x-cache: HIT' || fail 'second /history request was not a cache hit'

echo 'Checking only the History API can reach Postgres...'
if kubectl exec deploy/nginx -- nc -z -w 3 db 5432 2>/dev/null; then
    fail 'nginx pod can reach Postgres; the NetworkPolicy is not enforced'
fi

echo 'All end-to-end checks passed.'
