from datetime import datetime, timezone
from enum import Enum

from beanie import Document, Insert, Replace, Save, Update, before_event
from pydantic import Field
from pymongo import IndexModel


class AccessRequestStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class AccessRequestSource(str, Enum):
    CAREGIVER = "caregiver"
    PATIENT = "patient"


class CaregiverPatientAccess(Document):
    """Access mapping between caregivers and patients (soft-revocable)."""
    caregiver_id: str = Field(..., min_length=1)
    patient_id: str = Field(..., min_length=1)
    active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "caregiver_patient_access"
        indexes = [
            IndexModel([("caregiver_id", 1), ("patient_id", 1)], unique=True),
            IndexModel([("caregiver_id", 1), ("active", 1)]),
            IndexModel([("patient_id", 1), ("active", 1)]),
        ]

    @before_event(Insert, Replace, Save, Update)
    def _touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)


class CaregiverAccessRequest(Document):
    """Pending caregiver<->patient access handshake."""
    caregiver_id: str = Field(..., min_length=1)
    patient_id: str = Field(..., min_length=1)
    requested_by: AccessRequestSource
    status: AccessRequestStatus = AccessRequestStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "caregiver_access_requests"
        indexes = [
            IndexModel([("caregiver_id", 1), ("patient_id", 1)], unique=True),
            IndexModel([("patient_id", 1), ("status", 1), ("requested_by", 1)]),
            IndexModel([("caregiver_id", 1), ("status", 1), ("requested_by", 1)]),
        ]

    @before_event(Insert, Replace, Save, Update)
    def _touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)
