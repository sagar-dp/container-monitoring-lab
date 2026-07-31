"""
Sample Microservice with Prometheus Instrumentation
-----------------------------------------------------
A small Flask application that exposes a few demo endpoints and
instruments them with Prometheus metrics:

  - request_count       : total number of HTTP requests (Counter)
  - request_latency     : request duration histogram (Histogram)
  - in_progress_requests: number of requests currently being handled (Gauge)
  - app_info            : static info about the app (Info)

Metrics are exposed on GET /metrics in the standard Prometheus
text exposition format, ready to be scraped.
"""

import random
import time

from flask import Flask, jsonify, request
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    Info,
    generate_latest,
)

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Prometheus metric definitions
# ---------------------------------------------------------------------------

REQUEST_COUNT = Counter(
    "app_request_count",
    "Total number of HTTP requests",
    ["method", "endpoint", "http_status"],
)

REQUEST_LATENCY = Histogram(
    "app_request_latency_seconds",
    "Request latency in seconds",
    ["endpoint"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)

IN_PROGRESS = Gauge(
    "app_requests_in_progress",
    "Number of requests currently being processed",
)

APP_INFO = Info("app_build", "Build information for the microservice")
APP_INFO.info({"version": "1.0.0", "language": "python", "framework": "flask"})


# ---------------------------------------------------------------------------
# Middleware-style timing using before/after request hooks
# ---------------------------------------------------------------------------

@app.before_request
def before_request():
    request.start_time = time.time()
    IN_PROGRESS.inc()


@app.after_request
def after_request(response):
    latency = time.time() - request.start_time
    endpoint = request.path
    REQUEST_LATENCY.labels(endpoint=endpoint).observe(latency)
    REQUEST_COUNT.labels(
        method=request.method, endpoint=endpoint, http_status=response.status_code
    ).inc()
    IN_PROGRESS.dec()
    return response


# ---------------------------------------------------------------------------
# Application routes
# ---------------------------------------------------------------------------

@app.route("/")
def home():
    return jsonify(
        {
            "service": "sample-microservice",
            "status": "running",
            "endpoints": ["/", "/work", "/error", "/health", "/metrics"],
        }
    )


@app.route("/work")
def work():
    """Simulate variable processing time to generate interesting latency data."""
    delay = random.uniform(0.05, 0.6)
    time.sleep(delay)
    return jsonify({"message": "work complete", "simulated_delay_seconds": round(delay, 3)})


@app.route("/error")
def error():
    """Simulate an endpoint that sometimes fails, to generate 5xx metrics."""
    if random.random() < 0.3:
        return jsonify({"error": "simulated internal error"}), 500
    return jsonify({"message": "no error this time"})


@app.route("/health")
def health():
    return jsonify({"status": "healthy"}), 200


@app.route("/metrics")
def metrics():
    return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
