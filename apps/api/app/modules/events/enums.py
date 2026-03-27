from app.db.enums import StringEnum


class EventSeverity(StringEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class EventState(StringEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
