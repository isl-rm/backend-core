from enum import StrEnum


class Role(StrEnum):
    USER = "USER"
    ADMIN = "ADMIN"
    DOCTOR = "DOCTOR"
    NURSE = "NURSE"
    CAREGIVER = "CAREGIVER"
    DISPATCHER = "DISPATCHER"
    FIRST_RESPONDER = "FIRST_RESPONDER"


class UserStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"
    PENDING = "pending"
