# Monitoring Infrastructure Setup & Metric Collection Using Docker and Prometheus

A full monitoring stack for a containerized Python microservice, built with
Docker Compose. It demonstrates application-level, container-level, and
host-level observability using Prometheus, cAdvisor, Node Exporter, and
Grafana.

## Architecture

```
                        ┌─────────────────┐
                        │     Grafana      │  :3000
                        │  (dashboards)    │
                        └────────▲─────────┘
                                 │ queries
                        ┌────────┴─────────┐
                        │    Prometheus     │  :9090
                        │  (scrape+store)   │
                        └─┬───────┬───────┬─┘
              scrapes     │       │       │      scrapes
        ┌──────────────┐  │       │       │  ┌────────────────┐
        │ microservice │◄─┘       │       └─►│  node-exporter │  :9100
        │  (Flask app) │  :5000   │           │  (host metrics)│
        └──────────────┘          │           └────────────────┘
                                   │ scrapes
                          ┌────────▼─────────┐
                          │     cAdvisor      │  :8080
                          │ (container metrics)│
                          └────────────────────┘
```

## Components

| Component     | Role                                                            | Port |
|---------------|-------------------------------------------------------------------|------|
| microservice  | Sample Flask app instrumented with `prometheus_client`          | 5000 |
| Prometheus    | Scrapes & stores time-series metrics from all targets           | 9090 |
| cAdvisor      | Exposes per-container CPU/memory/network/disk metrics           | 8080 |
| Node Exporter | Exposes host-level system metrics (CPU, memory, disk, network)  | 9100 |
| Grafana       | Dashboards for visualizing everything Prometheus collects       | 3000 |

## Project Structure

```
monitoring-project/
├── app/
│   ├── app.py              # Flask microservice with Prometheus instrumentation
│   ├── requirements.txt    # Python dependencies
│   └── Dockerfile          # Container image for the microservice
├── prometheus/
│   └── prometheus.yml      # Scrape configuration for all targets
├── grafana/
│   └── provisioning/
│       ├── datasources/datasource.yml     # Auto-connects Grafana to Prometheus
│       └── dashboards/
│           ├── dashboard.yml              # Tells Grafana where to load dashboards
│           └── monitoring-overview.json   # Pre-built dashboard (8 panels)
├── docker-compose.yml      # Orchestrates all five services
└── README.md
```

## Prerequisites

- Docker Engine (20.10+)
- Docker Compose v2 (bundled with recent Docker Desktop/Engine)
- Linux/macOS/WSL2 host recommended (cAdvisor and Node Exporter mount host
  paths; on native Windows use WSL2)

## Getting Started

1. **Build and start the full stack**

   ```bash
   docker compose up -d --build
   ```

2. **Check that everything is running**

   ```bash
   docker compose ps
   ```

   You should see 5 containers: `microservice`, `prometheus`, `cadvisor`,
   `node-exporter`, `grafana`.

3. **Generate some traffic** so there's data to look at

   ```bash
   for i in $(seq 1 50); do curl -s http://localhost:5000/work > /dev/null; done
   for i in $(seq 1 20); do curl -s http://localhost:5000/error > /dev/null; done
   ```

4. **Explore the stack**

   | URL                                    | What you'll see                          |
   |-----------------------------------------|-------------------------------------------|
   | http://localhost:5000                  | Microservice root endpoint                |
   | http://localhost:5000/metrics          | Raw Prometheus metrics from the app       |
   | http://localhost:9090                  | Prometheus UI — try the queries below     |
   | http://localhost:9090/targets          | Confirm all scrape targets are "UP"       |
   | http://localhost:8080                  | cAdvisor UI (raw container metrics)       |
   | http://localhost:9100/metrics          | Raw Node Exporter metrics                 |
   | http://localhost:3000                  | Grafana (login: `admin` / `admin`)        |

   In Grafana, the **"Monitoring Overview"** dashboard is auto-provisioned —
   no manual setup needed. It's under Dashboards → Default.

5. **Stop the stack**

   ```bash
   docker compose down
   ```

   Add `-v` to also remove the Prometheus/Grafana data volumes:

   ```bash
   docker compose down -v
   ```

## Useful PromQL Queries

Try these in the Prometheus UI (http://localhost:9090/graph):

```promql
# Request rate per endpoint (requests/sec, 1-min window)
sum(rate(app_request_count_total[1m])) by (endpoint)

# 95th percentile latency per endpoint
histogram_quantile(0.95, sum(rate(app_request_latency_seconds_bucket[5m])) by (le, endpoint))

# Error rate (5xx responses per second)
sum(rate(app_request_count_total{http_status=~"5.."}[1m]))

# Container CPU usage by container name
sum(rate(container_cpu_usage_seconds_total{name!=""}[1m])) by (name)

# Container memory usage by container name
sum(container_memory_usage_bytes{name!=""}) by (name)

# Host CPU utilization percentage
100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[1m])) * 100)

# Host memory available
node_memory_MemAvailable_bytes
```

## How the Instrumentation Works

The Flask app (`app/app.py`) uses `prometheus_client` to define four metric
types:

- **Counter** (`app_request_count`) — total requests, labeled by method,
  endpoint, and status code. Counters only go up, which makes them ideal
  for computing rates with `rate()`.
- **Histogram** (`app_request_latency_seconds`) — request duration
  distribution, used to compute percentiles like p95/p99 latency.
- **Gauge** (`app_requests_in_progress`) — a value that can go up or down,
  used here to track concurrently in-flight requests.
- **Info** (`app_build`) — static key/value metadata about the build.

Flask's `before_request` / `after_request` hooks time every request and
record it against these metrics automatically, so no individual route has
to do bookkeeping itself. The `/metrics` endpoint exposes them all in the
Prometheus text format via `generate_latest()`.

## Extending This Project

- Add alerting rules to `prometheus/prometheus.yml` and run **Alertmanager**
  as an additional service to get notified on high error rates or latency.
- Add more application-specific metrics (queue depth, DB query time, cache
  hit rate) using the same Counter/Histogram/Gauge pattern.
- Swap the demo Flask app for a real service — as long as it exposes a
  `/metrics` endpoint in Prometheus format, this stack will pick it up.
- Point `prometheus.yml` at multiple microservice replicas for a more
  realistic multi-instance setup.

## Troubleshooting

- **cAdvisor fails to start on macOS/Windows**: cAdvisor relies on Linux
  cgroups and host paths that aren't available the same way outside Linux.
  Run this project inside WSL2 (Windows) or accept that some cAdvisor
  metrics may be limited on Docker Desktop for Mac.
- **Prometheus targets show "DOWN"**: check `docker compose logs <service>`
  and confirm the target container is on the `monitoring` network and
  listening on the expected port.
- **Grafana dashboard is empty**: confirm Prometheus has been scraping for
  at least a minute and that you've generated some traffic against the
  microservice (see step 3 above).
