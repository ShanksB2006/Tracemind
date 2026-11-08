"""Chaos injection scenarios simulating realistic distributed systems failures."""
from __future__ import annotations
import random
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Generator, Optional
from .models import LogEntry, LogLevel
from .topology import ServiceTopology


class BaseScenario:
    def __init__(self, topology: ServiceTopology):
        self.topology = topology

    def generate_tick(self, tick_second: int, total_seconds: int) -> List[LogEntry]:
        raise NotImplementedError


class PaymentDBExhaustionScenario(BaseScenario):
    """
    Scenario: Payment Service DB Connection Pool Exhaustion
    - Phase 1 (0 to 25% duration): Nominal healthy traffic.
    - Phase 2 (25% to 50% duration): Connection pool saturation begins, latency creeps from 120ms to 800ms.
    - Phase 3 (50% to 80% duration): CRITICAL failure - Pool exhausted, latency spikes to 4,800ms,
      ConnectionPoolTimeout exceptions, 500/504 cascades upstream to Order Service and API Gateway.
    - Phase 4 (80% to 100% duration): Recovery after pool reset, latencies normalize back to ~120ms.
    """

    def __init__(self, topology: ServiceTopology):
        super().__init__(topology)

    def generate_tick(self, tick_second: int, total_seconds: int, base_time: Optional[datetime] = None) -> List[LogEntry]:
        logs: List[LogEntry] = []
        if base_time is None:
            now_dt = datetime.now(timezone.utc)
        else:
            now_dt = base_time + timedelta(seconds=tick_second)
        now_str = now_dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        
        # Determine current phase
        ratio = tick_second / max(1, total_seconds)
        is_degrading = 0.25 <= ratio < 0.50
        is_failing = 0.50 <= ratio < 0.80
        is_recovering = ratio >= 0.80

        # Number of requests per second
        req_count = random.randint(3, 7)

        for _ in range(req_count):
            trace_id = uuid.uuid4().hex[:12]
            
            # 1. API Gateway log
            gw_span = uuid.uuid4().hex[:8]
            auth_span = uuid.uuid4().hex[:8]
            order_span = uuid.uuid4().hex[:8]
            pay_span = uuid.uuid4().hex[:8]
            db_span = uuid.uuid4().hex[:8]

            # Auth check (usually healthy)
            logs.append(LogEntry(
                timestamp=now_str,
                service="auth-service",
                level=LogLevel.INFO,
                message="JWT validated successfully for client_id=usr_9281",
                trace_id=trace_id,
                span_id=auth_span,
                latency_ms=random.uniform(8.0, 22.0),
                status_code=200
            ))

            if is_failing:
                # DATABASE FAILURE ROOT CAUSE
                db_latency = random.uniform(3500.0, 5200.0)
                logs.append(LogEntry(
                    timestamp=now_str,
                    service="postgres-db",
                    level=LogLevel.CRITICAL,
                    message="FATAL: remaining connection slots are reserved for non-replication superuser connections (active=100/100)",
                    trace_id=trace_id,
                    span_id=db_span,
                    latency_ms=db_latency,
                    status_code=503,
                    attributes={"pool_size": 100, "active_connections": 100, "waiting_queue": 42}
                ))

                # PAYMENT SERVICE (Directly affected downstream from DB)
                pay_latency = random.uniform(4200.0, 4950.0)
                logs.append(LogEntry(
                    timestamp=now_str,
                    service="payment-service",
                    level=LogLevel.ERROR,
                    message="ConnectionPoolTimeout: Timeout after 4000ms awaiting connection from pool [pool=payment-read-write, active=50/50]",
                    trace_id=trace_id,
                    span_id=pay_span,
                    latency_ms=pay_latency,
                    status_code=500,
                    attributes={"method": "POST", "endpoint": "/api/v1/payments/charge", "retry_count": 3}
                ))

                # ORDER SERVICE (Cascading 504 from Payment Service)
                order_latency = pay_latency + random.uniform(40.0, 90.0)
                logs.append(LogEntry(
                    timestamp=now_str,
                    service="order-service",
                    level=LogLevel.ERROR,
                    message="PaymentServiceClientException: Upstream payment-service timed out after 4800ms for order_id=ord_8829",
                    trace_id=trace_id,
                    span_id=order_span,
                    latency_ms=order_latency,
                    status_code=504,
                    attributes={"upstream": "payment-service", "order_id": "ord_8829"}
                ))

                # API GATEWAY (Tripping circuit breaker)
                logs.append(LogEntry(
                    timestamp=now_str,
                    service="api-gateway",
                    level=LogLevel.WARN,
                    message="CircuitBreaker OPEN for order-service. Returning HTTP 504 Gateway Timeout to client",
                    trace_id=trace_id,
                    span_id=gw_span,
                    latency_ms=order_latency + 15.0,
                    status_code=504
                ))

            elif is_degrading:
                # Degrading phase: DB pool saturation warning, response times climbing
                db_latency = random.uniform(400.0, 1100.0)
                logs.append(LogEntry(
                    timestamp=now_str,
                    service="postgres-db",
                    level=LogLevel.WARN,
                    message="High connection pool utilization: 88/100 connections active. Query queue depth: 8",
                    trace_id=trace_id,
                    span_id=db_span,
                    latency_ms=db_latency,
                    status_code=200
                ))

                pay_latency = db_latency + random.uniform(120.0, 300.0)
                logs.append(LogEntry(
                    timestamp=now_str,
                    service="payment-service",
                    level=LogLevel.WARN,
                    message=f"Slow query detected on payments table (duration={pay_latency:.1f}ms). Thread pool near capacity.",
                    trace_id=trace_id,
                    span_id=pay_span,
                    latency_ms=pay_latency,
                    status_code=200
                ))

                order_latency = pay_latency + 30.0
                logs.append(LogEntry(
                    timestamp=now_str,
                    service="order-service",
                    level=LogLevel.INFO,
                    message="Order processed with elevated latency",
                    trace_id=trace_id,
                    span_id=order_span,
                    latency_ms=order_latency,
                    status_code=200
                ))

                logs.append(LogEntry(
                    timestamp=now_str,
                    service="api-gateway",
                    level=LogLevel.INFO,
                    message="Request completed successfully",
                    trace_id=trace_id,
                    span_id=gw_span,
                    latency_ms=order_latency + 8.0,
                    status_code=200
                ))

            else:
                # Nominal healthy phase
                db_latency = random.uniform(12.0, 35.0)
                logs.append(LogEntry(
                    timestamp=now_str,
                    service="postgres-db",
                    level=LogLevel.DEBUG,
                    message="Transaction committed: INSERT INTO payments (id, amount, status) VALUES ($1, $2, 'SUCCESS')",
                    trace_id=trace_id,
                    span_id=db_span,
                    latency_ms=db_latency,
                    status_code=200
                ))

                pay_latency = random.uniform(90.0, 140.0)
                logs.append(LogEntry(
                    timestamp=now_str,
                    service="payment-service",
                    level=LogLevel.INFO,
                    message="Payment processed successfully for amount=$84.50",
                    trace_id=trace_id,
                    span_id=pay_span,
                    latency_ms=pay_latency,
                    status_code=200
                ))

                order_latency = pay_latency + random.uniform(25.0, 50.0)
                logs.append(LogEntry(
                    timestamp=now_str,
                    service="order-service",
                    level=LogLevel.INFO,
                    message="Order ord_4102 confirmed and inventory reserved",
                    trace_id=trace_id,
                    span_id=order_span,
                    latency_ms=order_latency,
                    status_code=200
                ))

                logs.append(LogEntry(
                    timestamp=now_str,
                    service="api-gateway",
                    level=LogLevel.INFO,
                    message="POST /api/v1/orders 200 OK",
                    trace_id=trace_id,
                    span_id=gw_span,
                    latency_ms=order_latency + 10.0,
                    status_code=200
                ))

        return logs


class MemoryLeakScenario(BaseScenario):
    """Scenario: Order service memory leak leading to OOM crash."""
    def generate_tick(self, tick_second: int, total_seconds: int, base_time: Optional[datetime] = None) -> List[LogEntry]:
        logs: List[LogEntry] = []
        if base_time is None:
            now_dt = datetime.now(timezone.utc)
        else:
            now_dt = base_time + timedelta(seconds=tick_second)
        now_str = now_dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        ratio = tick_second / max(1, total_seconds)
        trace_id = uuid.uuid4().hex[:12]

        if ratio > 0.65:
            # Critical OOM failure
            logs.append(LogEntry(
                timestamp=now_str,
                service="order-service",
                level=LogLevel.CRITICAL,
                message="java.lang.OutOfMemoryError: Java heap space. Dumping heap to java_pid1.hprof (Heap 98.9% full)",
                trace_id=trace_id,
                span_id=uuid.uuid4().hex[:8],
                latency_ms=8500.0,
                status_code=500
            ))
            logs.append(LogEntry(
                timestamp=now_str,
                service="api-gateway",
                level=LogLevel.ERROR,
                message="502 Bad Gateway: order-service connection refused (pod terminating)",
                trace_id=trace_id,
                span_id=uuid.uuid4().hex[:8],
                latency_ms=1200.0,
                status_code=502
            ))
        else:
            # Nominal with creeping memory
            logs.append(LogEntry(
                timestamp=now_str,
                service="order-service",
                level=LogLevel.INFO if ratio < 0.4 else LogLevel.WARN,
                message=f"Order cache size growing: {int(50000 * (1 + ratio * 4))} items. Heap usage at {int(40 + ratio * 55)}%",
                trace_id=trace_id,
                span_id=uuid.uuid4().hex[:8],
                latency_ms=random.uniform(50.0, 180.0),
                status_code=200
            ))

        return logs
