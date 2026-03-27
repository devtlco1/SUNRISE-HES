from app.db.enums import StringEnum


class CommunicationEndpointType(StringEnum):
    TCP = "tcp"
    SERIAL = "serial"
    MODEM = "modem"
    GATEWAY = "gateway"
    VIRTUAL = "virtual"


class ConnectivityTransportType(StringEnum):
    TCP_IP = "tcp_ip"
    SERIAL = "serial"
    MODEM = "modem"
    GATEWAY = "gateway"
    VIRTUAL = "virtual"


class SerialParity(StringEnum):
    NONE = "none"
    EVEN = "even"
    ODD = "odd"


class SerialStopBits(StringEnum):
    ONE = "one"
    ONE_POINT_FIVE = "one_point_five"
    TWO = "two"


class EndpointAssignmentStatus(StringEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class ProtocolFamily(StringEnum):
    DLMS_COSEM = "dlms_cosem"


class AssociationAuthenticationMode(StringEnum):
    NONE = "none"
    LOW = "low"
    HIGH = "high"
    HIGH_GMAC = "high_gmac"


class CredentialType(StringEnum):
    PASSWORD = "password"
    APN = "apn"
    TOKEN = "token"
    KEY_REF = "key_ref"


class ConnectivitySessionStatus(StringEnum):
    STARTED = "started"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"


class ConnectivitySessionPurpose(StringEnum):
    CONNECTIVITY_TEST = "connectivity_test"
    DEVICE_ONBOARDING = "device_onboarding"
    PROFILE_VALIDATION = "profile_validation"
    MANUAL_DIAGNOSTIC = "manual_diagnostic"
