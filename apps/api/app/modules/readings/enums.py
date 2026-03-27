from app.db.enums import StringEnum


class ReadingSourceType(StringEnum):
    MANUAL_READ = "manual_read"
    SCHEDULED_READ = "scheduled_read"
    COMMAND_RESULT = "command_result"
    IMPORT = "import"
    RUNTIME_POLL = "runtime_poll"


class ReadingBatchStatus(StringEnum):
    RECEIVED = "received"
    PROCESSED = "processed"
    FAILED = "failed"


class ReadingType(StringEnum):
    SCALAR = "scalar"
    REGISTER = "register"
    INSTANTANEOUS = "instantaneous"
    DEMAND = "demand"


class SnapshotType(StringEnum):
    BILLING = "billing"
    INSTANTANEOUS = "instantaneous"
    NAMEPLATE = "nameplate"
    CLOCK = "clock"
    DIAGNOSTICS = "diagnostics"


class ReadingQuality(StringEnum):
    GOOD = "good"
    ESTIMATED = "estimated"
    SUSPECT = "suspect"
    MISSING = "missing"
