from enum import Enum

from sqlalchemy import Enum as SqlEnum


class StringEnum(str, Enum):
    def __str__(self) -> str:
        return self.value


def enum_type(enum_class: type[StringEnum], *, name: str) -> SqlEnum:
    return SqlEnum(
        enum_class,
        name=name,
        native_enum=True,
        validate_strings=True,
        values_callable=lambda members: [member.value for member in members],
    )
