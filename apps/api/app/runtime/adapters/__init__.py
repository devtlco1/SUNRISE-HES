from app.modules.connectivity.enums import ProtocolFamily
from app.runtime.adapters.base import BaseRuntimeAdapter, RuntimeAdapter
from app.runtime.adapters.dlms_cosem import DlmsCosemRuntimeAdapter, GuruxDlmsAdapterBridge

_ADAPTERS: dict[str, BaseRuntimeAdapter] = {
    GuruxDlmsAdapterBridge.adapter_key: GuruxDlmsAdapterBridge(),
    DlmsCosemRuntimeAdapter.adapter_key: DlmsCosemRuntimeAdapter(),
}

_DEFAULT_PROTOCOL_ADAPTERS: dict[ProtocolFamily, str] = {
    ProtocolFamily.DLMS_COSEM: GuruxDlmsAdapterBridge.adapter_key,
}


def get_runtime_adapter(adapter_key: str) -> RuntimeAdapter:
    adapter = _ADAPTERS.get(adapter_key)
    if adapter is None:
        raise KeyError(f"Unknown runtime adapter '{adapter_key}'.")
    return adapter


def get_runtime_adapter_for_protocol(protocol_family: ProtocolFamily) -> RuntimeAdapter:
    adapter_key = _DEFAULT_PROTOCOL_ADAPTERS.get(protocol_family)
    if adapter_key is None:
        raise KeyError(f"No runtime adapter registered for protocol family '{protocol_family.value}'.")
    return get_runtime_adapter(adapter_key)


__all__ = [
    "BaseRuntimeAdapter",
    "DlmsCosemRuntimeAdapter",
    "GuruxDlmsAdapterBridge",
    "RuntimeAdapter",
    "get_runtime_adapter",
    "get_runtime_adapter_for_protocol",
]
