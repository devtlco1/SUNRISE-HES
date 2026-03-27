from app.db.enums import StringEnum


class JobCategory(StringEnum):
    COMMAND = "command"
    METER_READ = "meter_read"
    CONNECTIVITY_CHECK = "connectivity_check"
    SYSTEM_MAINTENANCE = "system_maintenance"


class JobTargetType(StringEnum):
    METER = "meter"
    ENDPOINT = "endpoint"
    SYSTEM = "system"


class JobScheduleType(StringEnum):
    MANUAL = "manual"
    ONCE = "once"
    CRON = "cron"
    INTERVAL = "interval"


class JobRunStatus(StringEnum):
    PENDING = "pending"
    CLAIMED = "claimed"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
