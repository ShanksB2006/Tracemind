"""Integration test verifying all FastAPI routes, RCA, and benchmark retrieval."""
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient
from backend.app.main import app

def run_tests():
    with TestClient(app) as client:
        # 1. Health
        res = client.get("/api/v1/health")
        assert res.status_code == 200
        print("[✓] Health Check:", res.json())

        # 2. Seeded Incidents
        incidents = client.get("/api/v1/incidents").json()
        assert len(incidents) > 0
        top_inc = incidents[-1]
        print("[✓] Active Incident:", top_inc["title"])
        print("    • Confidence:", f"{top_inc['confidence_percentage']}%")
        print("    • Root Cause:", top_inc["root_cause_identified"])
        print("    • Anomaly:", top_inc["anomaly_detected_summary"])
        print("    • Path:", top_inc["related_services_path"])

        # 3. Topology
        topo = client.get("/api/v1/topology").json()
        assert len(topo["nodes"]) >= 6
        print(f"[✓] Topology: {len(topo['nodes'])} nodes, {len(topo['edges'])} edges")

        # 4. Benchmarks
        bench = client.get("/api/v1/benchmarks").json()
        assert "results" in bench
        print(f"[✓] Benchmarks: {len(bench['results'])} models evaluated")
        for r in bench["results"]:
            print(f"    • {r['model_name']}: F1={r['f1_score']}, Latency={r['avg_inference_latency_ms']}ms")

        # 5. Frontend Index served
        frontend = client.get("/")
        assert frontend.status_code == 200
        print("[✓] Dashboard UI: Served 200 OK successfully")

if __name__ == "__main__":
    run_tests()
