Current status:
- Auth + RBAC + Audit completed
- Meter Registry completed
- Connectivity foundation completed
- Commands foundation completed
- Jobs/Scheduler foundation completed
- Worker execution bridge completed
- Scheduler materialization bridge completed
- Scheduler run generation completed
- Final scheduler-to-execution orchestration bridge completed
- Readings / Load Profiles / Event Ingestion foundation completed
- Protocol Runtime Foundation completed

Next required step:
- Worker Runtime Executor Foundation

Important constraints:
- Do not implement real socket communication yet
- Do not implement IEC handshakes yet
- Do not implement real HDLC framing yet
- Do not implement real Gurux sessions yet
- Do not implement Redis worker loop yet
- Do not add frontend work yet
- Do not redesign existing modules unless clearly necessary
- Preserve current module boundaries and migrations
- Prefer minimal safe changes