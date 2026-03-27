Current status:
- Auth + RBAC + Audit completed
- Meter Registry completed
- Connectivity foundation completed
- Commands foundation completed
- Jobs/Scheduler foundation completed
- Worker execution bridge completed
- Scheduler materialization completed
- Scheduler run generation completed

Next required step:
- Implement the final scheduler-to-execution orchestration bridge:
  generate JobRun -> materialize MeterCommand -> claim JobRun -> start CommandExecutionAttempt

Important constraints:
- Do not implement live DLMS/IEC/socket runtime yet
- Do not add frontend work yet
- Do not redesign existing modules unless necessary
- Preserve current module boundaries and migrations
- Prefer minimal safe changes