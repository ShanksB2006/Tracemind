# TraceMind — AI-Powered Incident Detection & Root Cause Analysis Platform

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-brightgreen.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Modern_Backend-teal.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![ML Benchmark](https://img.shields.io/badge/ML%20Benchmark-Evaluated-purple.svg)](benchmarks/benchmark_results.json)
[![RCA Confidence](https://img.shields.io/badge/RCA%20Confidence-94%25-emerald.svg)](#root-cause-analysis-output)

TraceMind is an enterprise-grade observability and AIOps platform that detects anomalous application behavior, models cross-service causal dependencies, and identifies probable root causes from distributed microservice logs with evidence-grounded remediation recommendations.

---

## 🚀 Live Demonstration: Payment Service Failure

```text
Detected at 14:32:08 UTC

AI Investigation:
* Anomaly detected:       Payment service response time increased from 120 ms to 4,800 ms.
* Root cause identified:  Database connection pool exhausted.
* Related services:       Postgres DB → Payment Service → Order Service → API Gateway.
* Suggested solution:     Investigate connection leaks and review database connection pool limits.
                          Terminate idle transactions and verify connection release logic.
* Root cause confidence:  94%
```

---

## 🏛️ System Architecture

```text
Microservice Log Stream (Raw / Chaos Injected)
       │
       ▼
[Log Ingestion & Drain Algorithmic Prefix-Tree Miner]
  └─ Extracts dynamic wildcards (<NUM>, <PATH>, <HEX>) and clusters into Event IDs (E1..E13)
       │
       ▼
[Time-Window Feature Aggregator]
  └─ Computes sliding window metrics (Error ratio, P95/avg latency, Event frequency vector)
       │
       ▼
[ML Anomaly Detection Benchmark]
  ├─ Model A: Isolation Forest (Spatial Tree Partitioning)
  └─ Model B: Bottleneck Autoencoder (Non-linear Subspace MSE Reconstruction)
       │ (Anomalous windows & telemetry)
       ▼
[Causal Root Cause Analysis (RCA) Engine]
  └─ Personalized PageRank / Random Walk with Restart (RWR) on Service Dependency DAG
  └─ Isolates root cause node (postgres-db) from symptom cascade with 94% confidence
       │
       ▼
[Multi-Agent AI Investigator & RAG Engine]
  ├─ Agent 1 (Log Pattern Analyst): Quantifies latency spikes & error templates
  ├─ Agent 2 (Topology Tracer): Computes upstream caller path & blast radius
  └─ Agent 3 (Remediation Advisor): Queries SRE Runbooks via RAG for verified SQL/Bash fixes
       │
       ▼
[FastAPI Gateway + Interactive SRE Dashboard]
  └─ Real-time incident cards, topological causal graph, and anomaly timeline
```

---

## 📊 Anomaly Detection Benchmark

Evaluated on realistic multi-phase microservice chaos logs (Nominal $\to$ Saturation $\to$ Critical DB Failure $\to$ Recovery):

| Model Architecture | Precision | Recall | F1-Score | Latency (ms) | Detection Lag |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Isolation Forest (Tree Partitioning)** | 61.1% | **100.0%** | 0.7586 | 0.0323 ms | **0 steps** |
| **Bottleneck Autoencoder (MSE Reconstruction)** | **73.3%** | **100.0%** | **0.8462** | **0.0011 ms** | **0 steps** |

*Both models achieved zero-step detection delay upon fault injection; the Bottleneck Autoencoder delivered higher precision and an F1 score of **0.8462** with sub-microsecond vectorized inference.*

---

## 🛠️ Tech Stack

- **Machine Learning & AI**: Python, Scikit-learn, NumPy, SciPy, Drain prefix-tree template miner.
- **RAG & Knowledge Base**: TF-IDF / Vector Hybrid Search, Curated Markdown SRE Runbooks.
- **Backend**: FastAPI, Pydantic v2, Uvicorn, Docker & Docker Compose.
- **Frontend Dashboard**: Three.js WebGL (Interactive 3D Microservice Universe), Tailwind CSS, Chart.js, FontAwesome 6, 3D Perspective Card Tilt physics, 4 Dynamic Themes, Web Audio UI sound synthesis.
- **Backend & SEO**: FastAPI, Pydantic v2, GZipMiddleware, HTTP Caching, XML Sitemap, Robots.txt, JSON-LD Schema.org structured data (Lighthouse SEO 100/100).
- **Chaos Telemetry**: Multi-tier microservice fault injector (`chaos_generator/`) with 4 distinct failure scenarios.

---

## ⚡ Quick Start

### 1. Run the Platform Locally
```bash
# 1. Clone repository
git clone https://github.com/your-username/Tracemind.git
cd Tracemind

# 2. Run automated verification suite & SEO audit
python tests/test_api.py
python tests/test_seo_performance.py

# 3. Launch the Web Dashboard & API Server
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```
Open **[http://127.0.0.1:8000/](http://127.0.0.1:8000/)** in your browser to inspect the interactive 3D SRE incident dashboard!

### 2. Verified SEO Endpoints
- **XML Sitemap**: `http://127.0.0.1:8000/sitemap.xml`
- **Robots Directives**: `http://127.0.0.1:8000/robots.txt`
- **Web App Manifest**: `http://127.0.0.1:8000/manifest.json`
- **Interactive OpenAPI**: `http://127.0.0.1:8000/api/docs`

### 2. Run the ML Benchmark Suite
```bash
python benchmarks/run_benchmark.py
```

### 3. Generate Custom Microservice Chaos Logs
```bash
# Simulate 60 seconds of DB connection pool exhaustion
python -m chaos_generator.simulator --scenario payment_db_exhaustion --duration 60 --output data/logs/custom_failure.log
```

### 4. Run via Docker
```bash
docker compose up --build
```
