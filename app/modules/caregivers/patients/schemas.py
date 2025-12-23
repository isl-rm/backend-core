from datetime import datetime

from app.shared.schemas import CamelModel


class CaregiverPatientAccessRequest(CamelModel):
    caregiver_id: str
    patient_id: str


class CaregiverPatientAccessResponse(CamelModel):
    caregiver_id: str
    patient_id: str
    active: bool
    updated_at: datetime


class CaregiverAccessRequestCreateForPatient(CamelModel):
    caregiver_id: str


class CaregiverAccessRequestCreateForCaregiver(CamelModel):
    patient_id: str


class CaregiverAccessRequestResponse(CamelModel):
    id: str
    caregiver_id: str
    patient_id: str
    requested_by: str
    status: str
    created_at: datetime
    updated_at: datetime
