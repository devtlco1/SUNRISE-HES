from __future__ import annotations

from pydantic import BaseModel

from app.db.enums import StringEnum


class RedisTransportAdminAction(StringEnum):
    BOOTSTRAP_CONSUMER_GROUP = "bootstrap_consumer_group"
    RESET_CONSUMER_GROUP = "reset_consumer_group"


class RedisTransportAdminStatus(StringEnum):
    CREATED = "created"
    ALREADY_EXISTS = "already_exists"
    RESET = "reset"


class RedisTransportAdminResult(BaseModel):
    backend_name: str = "redis"
    action: RedisTransportAdminAction
    status: RedisTransportAdminStatus
    stream_name: str
    consumer_group_name: str
    stream_exists: bool
    consumer_group_exists_before: bool
    consumer_group_exists_after: bool
    consumer_count_before: int = 0
    pending_count_before: int = 0
    summary: str
