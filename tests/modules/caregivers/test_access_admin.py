import pytest
from bson import ObjectId
from httpx import AsyncClient

from app.shared.constants import Role
from tests.modules.caregivers.helpers import auth_headers


@pytest.mark.asyncio
async def test_admin_grant_and_revoke_access(
    client: AsyncClient, create_user_func
) -> None:
    admin = await create_user_func(id=str(ObjectId()), roles=[Role.ADMIN])
    caregiver = await create_user_func(id=str(ObjectId()), roles=[Role.CAREGIVER])
    patient = await create_user_func(id=str(ObjectId()), roles=[Role.USER])

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
    data = resp.json()
    assert data["caregiverId"] == str(caregiver.id)
    assert data["patientId"] == str(patient.id)
    assert data["active"] is True

    resp = await client.get(
        "/api/v1/caregivers/patients",
        headers=auth_headers(str(caregiver.id)),
    )
    assert resp.status_code == 200
    patients = resp.json()
    assert [patient["id"] for patient in patients] == [str(patient.id)]

    resp = await client.request(
        "DELETE",
        "/api/v1/caregivers/access",
        json=payload,
        headers=auth_headers(str(admin.id)),
    )
    assert resp.status_code == 200
    assert resp.json()["active"] is False

    resp = await client.get(
        "/api/v1/caregivers/patients",
        headers=auth_headers(str(caregiver.id)),
    )
    assert resp.status_code == 200
    assert resp.json() == []
