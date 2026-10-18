import json
import os
import sys
import time
import uuid
from collections import deque

from fastapi import FastAPI, Request
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest, CollectorRegistry

EMAIL = os.environ.get("EMAIL", "23f3000733@ds.study.iitm.ac.in")
START = time.time()

registry = CollectorRegistry()
# prometheus_client exposes this as `http_requests_total`
REQS = Counter("http_requests", "Total HTTP requests", registry=registry)

LOGS: deque = deque(maxlen=1000)

app = FastAPI()


@app.middleware("http")
async def observe(request: Request, call_next):
    REQS.inc()
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex
    t0 = time.time()
    level = "INFO"
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        if status >= 500:
            level = "ERROR"
        elif status >= 400:
            level = "WARNING"
        response.headers["x-request-id"] = rid
        return response
    except Exception:
        level = "ERROR"
        raise
    finally:
        entry = {
            "level": level,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + "Z",
            "path": request.url.path,
            "request_id": rid,
            "method": request.method,
            "status": status,
            "duration_ms": round((time.time() - t0) * 1000, 3),
        }
        LOGS.append(entry)
        print(json.dumps(entry), file=sys.stdout, flush=True)


@app.get("/work")
def work(n: int = 1):
    n = max(0, min(n, 1_000_000))
    acc = 0
    for i in range(n):
        acc += i * i
    return {"email": EMAIL, "done": n}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)


@app.get("/healthz")
def healthz():
    return {"status": "ok", "uptime_s": max(0.0, time.time() - START)}


@app.get("/logs/tail")
def logs_tail(limit: int = 10):
    limit = max(0, limit)
    items = list(LOGS)
    return items[-limit:] if limit else []
