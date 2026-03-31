from app.db.enums import StringEnum


class CommandCategory(StringEnum):
    REMOTE_DISCONNECT = "remote_disconnect"
    REMOTE_RECONNECT = "remote_reconnect"
    ON_DEMAND_READ = "on_demand_read"
    CLOCK_SYNC = "clock_sync"
    PROFILE_CAPTURE = "profile_capture"
    CONNECTIVITY_TEST = "connectivity_test"
    CONFIG_PUSH = "config_push"


class CommandTargetScope(StringEnum):
    METER = "meter"


class CommandStatus(StringEnum):
    PENDING = "pending"
    SCHEDULED = "scheduled"
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    RETRY_WAIT = "retry_wait"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class CommandExecutionAttemptStatus(StringEnum):
    STARTED = "started"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class CommandPriority(StringEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class RelayControlCommandOperation(StringEnum):
    DISCONNECT = "disconnect"
    RECONNECT = "reconnect"


class OnDemandReadCommandOperation(StringEnum):
    READ_BILLING_SNAPSHOT = "read_billing_snapshot"


class CommandOperationalFamily(StringEnum):
    PROFILE_CAPTURE = "profile_capture"
    RELAY_CONTROL = "relay_control"
    ON_DEMAND_READ = "on_demand_read"
