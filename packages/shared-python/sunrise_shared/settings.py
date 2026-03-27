from dataclasses import dataclass


@dataclass(frozen=True)
class PlatformIdentity:
    project_name: str = "sunrise-hes-platform"
    domain: str = "hes"
