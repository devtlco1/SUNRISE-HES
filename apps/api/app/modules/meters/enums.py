from app.db.enums import StringEnum


class PhaseType(StringEnum):
    SINGLE_PHASE = "single_phase"
    THREE_PHASE = "three_phase"


class MeterCategory(StringEnum):
    ELECTRICITY = "electricity"
    WATER = "water"
    GAS = "gas"
    HEAT = "heat"


class TransportType(StringEnum):
    TCP_IP = "tcp_ip"
    CELLULAR = "cellular"
    RS485 = "rs485"
    PLC = "plc"


class IPMode(StringEnum):
    STATIC = "static"
    DHCP = "dhcp"
    PRIVATE_APN = "private_apn"


class AuthenticationMode(StringEnum):
    NONE = "none"
    PAP = "pap"
    CHAP = "chap"
    TLS_PSK = "tls_psk"


class MeterLifecycleStatus(StringEnum):
    REGISTERED = "registered"
    COMMISSIONED = "commissioned"
    ACTIVE = "active"
    INACTIVE = "inactive"
    RETIRED = "retired"
