"""Cross-database compatible column types (works on SQLite + PostgreSQL)."""
import uuid
import json

from sqlalchemy import CHAR, Text, TypeDecorator
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID


class UUIDType(TypeDecorator):
    """UUID column — uses native UUID on Postgres, CHAR(36) on SQLite."""

    impl = CHAR
    cache_ok = True

    def __init__(self, as_uuid: bool = True, **kw):
        super().__init__(length=36)
        self.as_uuid = as_uuid

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=self.as_uuid))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value
        if isinstance(value, uuid.UUID):
            return str(value)
        return str(uuid.UUID(str(value)))

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value if self.as_uuid else str(value)
        try:
            u = uuid.UUID(str(value))
            return u if self.as_uuid else str(u)
        except (ValueError, AttributeError):
            return value


class JSONType(TypeDecorator):
    """JSON column — uses JSONB on Postgres, Text on SQLite."""

    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value
        return json.dumps(value, default=str)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value
        if isinstance(value, (dict, list)):
            return value
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return value
