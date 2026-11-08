# SRE Runbook: PostgreSQL Connection Pool Exhaustion

## Incident Symptoms
- Logs contain: `FATAL: remaining connection slots are reserved for non-replication superuser connections`
- Application logs contain: `ConnectionPoolTimeout: Timeout after <*>ms awaiting connection from pool`
- Downstream services experience elevated response times (e.g. 120ms spiking to 4,800ms) followed by HTTP 500 or HTTP 504 Gateway Timeouts.

## Root Cause Analysis
PostgreSQL instances enforce a maximum connection ceiling governed by `max_connections`. When microservices fail to return connections to the pool (connection leak) or under sudden traffic spikes without backpressure, all connection slots become occupied. New transaction threads block until timeout.

## Immediate Remediation Steps
1. **Terminate idle or long-running leaked transactions**:
   ```sql
   SELECT pid, now() - pg_stat_activity.query_start AS duration, query, state
   FROM pg_stat_activity
   WHERE (now() - pg_stat_activity.query_start) > interval '5 minutes'
     AND state != 'idle';

   -- Terminate offending backend connection:
   SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle in transaction' AND query_start < now() - interval '2 minutes';
   ```

2. **Increase Database Connection Pool Limits**:
   - Check current limit: `SHOW max_connections;`
   - Dynamically scale PgBouncer or connection pooler max client connections.
   - Increase application pool (`maximumPoolSize`) in HikariCP / SQLAlchemy to match workload concurrency.

3. **Verify and Prevent Connection Leaks**:
   - Audit code for unclosed transactions or missing `finally { conn.close(); }` / context manager blocks.
   - Configure connection leak detection thresholds:
     ```yaml
     hikari:
       leak-detection-threshold: 2000 # 2 seconds
       connection-timeout: 5000       # 5 seconds
       max-lifetime: 1800000          # 30 minutes
     ```
