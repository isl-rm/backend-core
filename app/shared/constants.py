from enum import Enum


class Role(str, Enum):
    USER = "USER" # OR PATIENT
    ADMIN = "ADMIN"
    DOCTOR = "DOCTOR"
    NURSE = "NURSE"
    CAREGIVER = "CAREGIVER"
    DISPATCHER = "DISPATCHER"
    FIRST_RESPONDER = "FIRST_RESPONDER"


class UserStatus(str, Enum):
    ACTIVE = "active"
    DISABLED = "disabled"
    PENDING = "pending"
