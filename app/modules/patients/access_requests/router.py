from typing import List

from fastapi import APIRouter, Depends

from app.modules.caregivers.patients.schemas import CaregiverAccessRequestResponse
from app.modules.caregivers.patients.service import CaregiverAccessRequestService
from app.modules.users.models import User
from app.shared import deps
from app.shared.constants import Role

router = APIRouter()


@router.get(
    "/access-requests/incoming",
    response_model=List[CaregiverAccessRequestResponse],
    summary="List incoming caregiver access requests",
)
async def list_incoming_access_requests_for_patient(
    current_user: User = Depends(deps.RoleChecker([Role.USER], allow_admin=False)),
    service: CaregiverAccessRequestService = Depends(CaregiverAccessRequestService),
) -> List[CaregiverAccessRequestResponse]:
    requests = await service.list_incoming_for_patient(current_user)
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
