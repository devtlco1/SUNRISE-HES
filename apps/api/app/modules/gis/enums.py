from app.db.enums import StringEnum


class AssetStatus(StringEnum):
    PLANNED = "planned"
    ACTIVE = "active"
    INACTIVE = "inactive"
    RETIRED = "retired"
