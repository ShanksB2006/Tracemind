# SRE Runbook: JVM Memory Leak and OutOfMemoryError (OOM)

## Incident Symptoms
- Microservice logs contain: `java.lang.OutOfMemoryError: Java heap space. Dumping heap to java_pid1.hprof`
- Garbage collection pauses (Stop-the-World) exceed 4,000ms.
- Pod crash loops or memory threshold triggers termination (`ExitCode 137 / OOMKilled`).
- Upstream API Gateway reports `502 Bad Gateway` or `504 Gateway Timeout` as order-service connections drop.

## Root Cause Analysis
Unbounded object accumulation in memory caches, unclosed resource handles, or infinite thread-local collections lead to continuous heap consumption exceeding container limits (`-Xmx`). Once JVM Old Generation hits 98%+, GC thrashing starves application request threads.

## Immediate Remediation Steps
1. **Trigger Rolling Pod Restart to Evacuate Memory Pressure**:
   ```bash
   kubectl rollout restart deployment/order-service -n production
   kubectl rollout status deployment/order-service -n production --timeout=60s
   ```

2. **Capture Heap Dump and Profile Active Memory**:
   ```bash
   jcmd $(pgrep -f order-service) GC.heap_dump /tmp/order_heap_$(date +%s).hprof
   jcmd $(pgrep -f order-service) Thread.print > /tmp/thread_dump.txt
   ```

3. **Temporarily Scale Memory Request and Limit**:
   ```bash
   kubectl set resources deployment/order-service -n production \
     --limits=memory=4Gi,cpu=2000m \
     --requests=memory=2Gi,cpu=1000m
   ```

4. **Verify Memory Normalization and Request Latency**:
   ```bash
   kubectl top pods -l app=order-service -n production
   curl -s -o /dev/null -w "%{http_code} %{time_total}s\n" https://api.tracemind.internal/api/v1/orders/health
   ```
