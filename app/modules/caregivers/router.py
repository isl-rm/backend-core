from fastapi import APIRouter

from app.modules.caregivers.alerts import router as alerts_router
from app.modules.caregivers.patient_conditions import router as conditions_router
from app.modules.caregivers.patients import router as patients_router
from app.modules.caregivers.vitals import router as vitals_router

router = APIRouter(prefix="/caregivers")
router.include_router(patients_router.router, tags=["caregivers"])
router.include_router(conditions_router.router, tags=["caregivers"])
router.include_router(vitals_router.router, tags=["caregivers"])
router.include_router(alerts_router.router, tags=["caregivers"])

__all__ = ["router"]
