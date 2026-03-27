from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol

from app.modules.connectivity.enums import ProtocolFamily
from app.runtime.contracts import ProtocolExecutionPlan, RuntimeCommandRequest, RuntimeCommandResult


class RuntimeAdapter(Protocol):
    adapter_key: str
    supported_protocol_families: tuple[ProtocolFamily, ...]

    def supports_plan(self, plan: ProtocolExecutionPlan) -> bool: ...

    def build_request(self, plan: ProtocolExecutionPlan) -> RuntimeCommandRequest: ...

    def execute(self, plan: ProtocolExecutionPlan) -> RuntimeCommandResult: ...


class BaseRuntimeAdapter(ABC):
    adapter_key = "base-runtime-adapter"
    supported_protocol_families: tuple[ProtocolFamily, ...] = ()

    def supports_plan(self, plan: ProtocolExecutionPlan) -> bool:
        return plan.protocol_family in self.supported_protocol_families

    def build_request(self, plan: ProtocolExecutionPlan) -> RuntimeCommandRequest:
        return plan.command

    @abstractmethod
    def execute(self, plan: ProtocolExecutionPlan) -> RuntimeCommandResult:
        raise NotImplementedError("Runtime execution is not implemented in the protocol foundation phase.")
