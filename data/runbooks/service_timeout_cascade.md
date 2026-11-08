# SRE Runbook: Cascading Upstream Service Timeout & Circuit Breaking

## Incident Symptoms
- Edge Gateway returns HTTP 504 Gateway Timeout or 502 Bad Gateway.
- Logs contain: `CircuitBreaker OPEN for <service>. Returning HTTP 504 Gateway Timeout`.
- High P95/P99 latency cascades upward through API Gateway and Order Service.

## Root Cause Analysis
A slow or non-responsive downstream service blocks worker threads in upstream calling services. In the absence of strict request deadlines and circuit breakers, upstream connection queues saturate, causing a cascade failure across the entire dependency graph.

## Immediate Remediation Steps
1. **Enable Circuit Breaking & Fail-Fast Fallbacks**:
   - Trip circuit breaker manually to isolate the failing downstream dependency and protect core services:
     ```bash
     curl -X POST http://api-gateway:8080/actuator/circuitbreakers/order-service/trip
     ```
2. **Tune Call Timeouts & Exponential Backoff**:
   - Reduce synchronous HTTP/gRPC timeouts to $<1000\text{ms}$ with jittered backoff.
   - Prevent retry storms by introducing a token-bucket rate limiter.
3. **Scale Upstream Thread Pools**:
   - Temporarily increase worker thread pool capacity on edge proxy and intermediary microservices.
