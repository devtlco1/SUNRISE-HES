from app.db.enums import StringEnum


class UserStatus(StringEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    LOCKED = "locked"
    SUSPENDED = "suspended"
