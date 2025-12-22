from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from app.modules.caregivers.conditions.models import ConditionSeverity
from app.modules.caregivers.patients.models import AccessRequestSource
from app.modules.caregivers.patients.schemas import (
    CaregiverAccessRequestCreateForCaregiver,
    CaregiverAccessRequestCreateForPatient,
    CaregiverAccessRequestResponse,
    CaregiverPatientAccessRequest,
    CaregiverPatientAccessResponse,
)
from app.modules.caregivers.patients.service import (
    CaregiverAccessRequestService,
    CaregiverPatientService,
)
from app.modules.users.models import User
from app.modules.users.schemas import UserResponse
from app.shared import deps
from app.shared.constants import Role

router = APIRouter()


@router.get(
    "/patients",
    response_model=List[UserResponse],
    summary="List patients for caregiver",
)
async def list_caregiver_patients(
    current_user: User = Depends(deps.RoleChecker([Role.CAREGIVER])),
    service: CaregiverPatientService = Depends(CaregiverPatientService),
) -> List[UserResponse]:
    return await service.list_patients(current_user)


@router.get(
    "/patients/moderate",
    response_model=List[UserResponse],
    summary="List moderate-condition patients for caregiver",
)
async def list_caregiver_patients_moderate(
    current_user: User = Depends(deps.RoleChecker([Role.CAREGIVER])),
    service: CaregiverPatientService = Depends(CaregiverPatientService),
) -> List[UserResponse]:
    return await service.list_patients_by_severity(
        current_user, ConditionSeverity.MODERATE
    )


@router.get(
    "/patients/critical",
    response_model=List[UserResponse],
    summary="List critical-condition patients for caregiver",
)
async def list_caregiver_patients_critical(
    current_user: User = Depends(deps.RoleChecker([Role.CAREGIVER])),
    service: CaregiverPatientService = Depends(CaregiverPatientService),
) -> List[UserResponse]:
    return await service.list_patients_by_severity(
        current_user, ConditionSeverity.CRITICAL
    )


@router.post(
    "/access",
    response_model=CaregiverPatientAccessResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Grant caregiver access to a patient",
)
async def grant_caregiver_access(
    payload: CaregiverPatientAccessRequest,
    current_user: User = Depends(deps.RoleChecker([Role.ADMIN])),
    service: CaregiverPatientService = Depends(CaregiverPatientService),
) -> CaregiverPatientAccessResponse:
    access = await service.grant_access(payload.caregiver_id, payload.patient_id)
    return CaregiverPatientAccessResponse(
        caregiver_id=access.caregiver_id,
        patient_id=access.patient_id,
        active=access.active,
        updated_at=access.updated_at,
    )


@router.delete(
    "/access",
    response_model=CaregiverPatientAccessResponse,
    summary="Revoke caregiver access to a patient",
)
async def revoke_caregiver_access(
    payload: CaregiverPatientAccessRequest,
    current_user: User = Depends(deps.RoleChecker([Role.ADMIN])),
    service: CaregiverPatientService = Depends(CaregiverPatientService),
) -> CaregiverPatientAccessResponse:
    access = await service.revoke_access(payload.caregiver_id, payload.patient_id)
    if not access:
        raise HTTPException(status_code=404, detail="Access mapping not found")
    return CaregiverPatientAccessResponse(
        caregiver_id=access.caregiver_id,
        patient_id=access.patient_id,
        active=access.active,
        updated_at=access.updated_at,
    )


@router.post(
    "/access-requests/caregiver",
    response_model=CaregiverAccessRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Caregiver requests access to a patient",
)
async def request_access_as_caregiver(
    payload: CaregiverAccessRequestCreateForCaregiver,
    current_user: User = Depends(deps.RoleChecker([Role.CAREGIVER], allow_admin=False)),
    service: CaregiverAccessRequestService = Depends(CaregiverAccessRequestService),
) -> CaregiverAccessRequestResponse:
    patient_user = await User.get(payload.patient_id)
    if not patient_user or Role.CAREGIVER in patient_user.roles:
        raise HTTPException(status_code=400, detail="Patient not found")
    try:
        access_request = await service.create_request(
            caregiver_id=str(current_user.id),
            patient_id=payload.patient_id,
            requested_by=AccessRequestSource.CAREGIVER,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CaregiverAccessRequestResponse(
        id=str(access_request.id),
        caregiver_id=access_request.caregiver_id,
        patient_id=access_request.patient_id,
        requested_by=access_request.requested_by.value,
        status=access_request.status.value,
        created_at=access_request.created_at,
        updated_at=access_request.updated_at,
    )


@router.post(
    "/access-requests/patient",
    response_model=CaregiverAccessRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Patient invites a caregiver",
)
async def request_access_as_patient(
    payload: CaregiverAccessRequestCreateForPatient,
    current_user: User = Depends(deps.RoleChecker([Role.USER], allow_admin=False)),
    service: CaregiverAccessRequestService = Depends(CaregiverAccessRequestService),
) -> CaregiverAccessRequestResponse:
    caregiver_user = await User.get(payload.caregiver_id)
    if not caregiver_user or Role.CAREGIVER not in caregiver_user.roles:
        raise HTTPException(status_code=400, detail="Caregiver not found")
    try:
        access_request = await service.create_request(
            caregiver_id=payload.caregiver_id,
            patient_id=str(current_user.id),
            requested_by=AccessRequestSource.PATIENT,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CaregiverAccessRequestResponse(
        id=str(access_request.id),
        caregiver_id=access_request.caregiver_id,
        patient_id=access_request.patient_id,
        requested_by=access_request.requested_by.value,
        status=access_request.status.value,
        created_at=access_request.created_at,
        updated_at=access_request.updated_at,
    )


@router.get(
    "/access-requests/incoming",
    response_model=List[CaregiverAccessRequestResponse],
    summary="List incoming patient access requests",
)
async def list_incoming_access_requests(
    current_user: User = Depends(deps.RoleChecker([Role.CAREGIVER], allow_admin=False)),
    service: CaregiverAccessRequestService = Depends(CaregiverAccessRequestService),
) -> List[CaregiverAccessRequestResponse]:
    requests = await service.list_incoming_for_caregiver(current_user)
    return [
        CaregiverAccessRequestResponse(
            id=str(item.id),
            caregiver_id=item.caregiver_id,
            patient_id=item.patient_id,
            requested_by=item.requested_by.value,
            status=item.status.value,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
        for item in requests
    ]


@router.post(
    "/access-requests/{request_id}/accept",
    response_model=CaregiverAccessRequestResponse,
    summary="Accept a caregiver/patient access request",
)
async def accept_access_request(
    request_id: str,
    current_user: User = Depends(deps.get_current_user),
    request_service: CaregiverAccessRequestService = Depends(
        CaregiverAccessRequestService
    ),
    patient_service: CaregiverPatientService = Depends(CaregiverPatientService),
) -> CaregiverAccessRequestResponse:
    try:
        access_request = await request_service.accept_request(
            request_id, current_user, patient_service
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CaregiverAccessRequestResponse(
        id=str(access_request.id),
        caregiver_id=access_request.caregiver_id,
        patient_id=access_request.patient_id,
        requested_by=access_request.requested_by.value,
        status=access_request.status.value,
        created_at=access_request.created_at,
        updated_at=access_request.updated_at,
    )
