from typing import Iterable, List, Optional

from beanie.operators import In
from bson import ObjectId

from app.modules.caregivers.patient_conditions.models import ConditionSeverity, PatientCondition
from app.modules.caregivers.patients.models import (
    AccessRequestSource,
    AccessRequestStatus,
    CaregiverAccessRequest,
    CaregiverPatientAccess,
)
from app.modules.users.models import User
from app.shared.constants import Role


class CaregiverPatientService:
    async def grant_access(
        self, caregiver_id: str, patient_id: str
    ) -> CaregiverPatientAccess:
        existing = await CaregiverPatientAccess.find_one(
            CaregiverPatientAccess.caregiver_id == caregiver_id,
            CaregiverPatientAccess.patient_id == patient_id,
        )
        if existing:
            if not existing.active:
                existing.active = True
                await existing.save()
            return existing

        access = CaregiverPatientAccess(
            caregiver_id=caregiver_id,
            patient_id=patient_id,
            active=True,
        )
        await access.insert()
        return access

    async def revoke_access(
        self, caregiver_id: str, patient_id: str
    ) -> Optional[CaregiverPatientAccess]:
        existing = await CaregiverPatientAccess.find_one(
            CaregiverPatientAccess.caregiver_id == caregiver_id,
            CaregiverPatientAccess.patient_id == patient_id,
        )
        if not existing:
            return None
        if existing.active:
            existing.active = False
            await existing.save()
        return existing

    async def list_patient_ids(self, caregiver: User) -> List[str]:
        links = await CaregiverPatientAccess.find(
            CaregiverPatientAccess.caregiver_id == str(caregiver.id),
            CaregiverPatientAccess.active == True,
        ).to_list()
        if not links:
            return []
        return list({link.patient_id for link in links})

    async def list_patients(self, caregiver: User) -> List[User]:
        patient_ids = await self.list_patient_ids(caregiver)
        return await self._load_users(patient_ids)

    async def list_patients_by_severity(
        self, caregiver: User, severity: ConditionSeverity
    ) -> List[User]:
        patient_ids = await self.list_patient_ids(caregiver)
        if not patient_ids:
            return []
        # Filter only the authorized patients whose latest condition matches the severity.
        conditions = await PatientCondition.find(
            In(PatientCondition.patient_id, patient_ids),
            PatientCondition.severity == severity,
        ).to_list()
        if not conditions:
            return []
        filtered_ids = {condition.patient_id for condition in conditions}
        return await self._load_users(filtered_ids)

    async def _load_users(self, patient_ids: Iterable[str]) -> List[User]:
        object_ids = self._to_object_ids(patient_ids)
        if not object_ids:
            return []
        return await User.find(In(User.id, object_ids)).to_list()

    def _to_object_ids(self, patient_ids: Iterable[str]) -> List[ObjectId]:
        # Convert stored string IDs to ObjectId for the User query.
        object_ids: List[ObjectId] = []
        for patient_id in patient_ids:
            try:
                object_ids.append(ObjectId(str(patient_id)))
            except Exception:
                continue
        return object_ids


class CaregiverAccessRequestService:
    async def create_request(
        self, caregiver_id: str, patient_id: str, requested_by: AccessRequestSource
    ) -> CaregiverAccessRequest:
        existing = await CaregiverAccessRequest.find_one(
            CaregiverAccessRequest.caregiver_id == caregiver_id,
            CaregiverAccessRequest.patient_id == patient_id,
        )
        if existing:
            if existing.status == AccessRequestStatus.ACCEPTED:
                raise ValueError("Access already granted")
            existing.requested_by = requested_by
            existing.status = AccessRequestStatus.PENDING
            await existing.save()
            return existing

        access_request = CaregiverAccessRequest(
            caregiver_id=caregiver_id,
            patient_id=patient_id,
            requested_by=requested_by,
            status=AccessRequestStatus.PENDING,
        )
        await access_request.insert()
        return access_request

    async def list_incoming_for_caregiver(
        self, caregiver: User
    ) -> List[CaregiverAccessRequest]:
        if Role.CAREGIVER not in caregiver.roles and Role.ADMIN not in caregiver.roles:
            return []
        return await CaregiverAccessRequest.find(
            CaregiverAccessRequest.caregiver_id == str(caregiver.id),
            CaregiverAccessRequest.status == AccessRequestStatus.PENDING,
            CaregiverAccessRequest.requested_by == AccessRequestSource.PATIENT,
        ).to_list()

    async def list_incoming_for_patient(
        self, patient: User
    ) -> List[CaregiverAccessRequest]:
        return await CaregiverAccessRequest.find(
            CaregiverAccessRequest.patient_id == str(patient.id),
            CaregiverAccessRequest.status == AccessRequestStatus.PENDING,
            CaregiverAccessRequest.requested_by == AccessRequestSource.CAREGIVER,
        ).to_list()

    async def accept_request(
        self, request_id: str, user: User, patient_service: CaregiverPatientService
    ) -> CaregiverAccessRequest:
        access_request = await CaregiverAccessRequest.get(request_id)
        if not access_request:
            raise ValueError("Access request not found")
        if access_request.status != AccessRequestStatus.PENDING:
            raise ValueError("Access request is not pending")

        if access_request.requested_by == AccessRequestSource.CAREGIVER:
            if str(user.id) != access_request.patient_id:
                raise PermissionError("Not allowed to accept this request")
        else:
            if str(user.id) != access_request.caregiver_id:
                raise PermissionError("Not allowed to accept this request")
            if Role.CAREGIVER not in user.roles and Role.ADMIN not in user.roles:
                raise PermissionError("Not allowed to accept this request")

        access_request.status = AccessRequestStatus.ACCEPTED
        await access_request.save()
        await patient_service.grant_access(
            caregiver_id=access_request.caregiver_id,
            patient_id=access_request.patient_id,
        )
        return access_request
