import pytest
from app.modules.caregivers.conditions.models import ConditionSeverity, PatientCondition
from bson import ObjectId
from httpx import AsyncClient

from app.shared.constants import Role
from tests.modules.caregivers.helpers import auth_headers


@pytest.mark.asyncio
async def test_caregiver_patients_filtered_by_condition(
    client: AsyncClient, create_user_func
) -> None:
    admin = await create_user_func(id=str(ObjectId()), roles=[Role.ADMIN])
    caregiver = await create_user_func(id=str(ObjectId()), roles=[Role.CAREGIVER])
    patient_moderate = await create_user_func(id=str(ObjectId()), roles=[Role.USER])
    patient_critical = await create_user_func(id=str(ObjectId()), roles=[Role.USER])

    for patient in (patient_moderate, patient_critical):
        payload = {
            "caregiverId": str(caregiver.id),
            "patientId": str(patient.id),
        }
        resp = await client.post(
            "/api/v1/caregivers/access",
            json=payload,
            headers=auth_headers(str(admin.id)),
        )
        assert resp.status_code == 201

    await PatientCondition(
        patient_id=str(patient_moderate.id),
        severity=ConditionSeverity.MODERATE,
    ).insert()
    await PatientCondition(
        patient_id=str(patient_critical.id),
        severity=ConditionSeverity.CRITICAL,
    ).insert()

    resp = await client.get(
        "/api/v1/caregivers/patients/moderate",
        headers=auth_headers(str(caregiver.id)),
    )
    assert resp.status_code == 200
    assert [item["id"] for item in resp.json()] == [str(patient_moderate.id)]

    resp = await client.get(
        "/api/v1/caregivers/patients/critical",
        headers=auth_headers(str(caregiver.id)),
    )
    assert resp.status_code == 200
    assert [item["id"] for item in resp.json()] == [str(patient_critical.id)]
