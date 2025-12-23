import pytest
from bson import ObjectId
from httpx import AsyncClient

from app.shared.constants import Role
from tests.modules.caregivers.helpers import auth_headers


@pytest.mark.asyncio
async def test_caregiver_request_flow(
    client: AsyncClient, create_user_func
) -> None:
    caregiver = await create_user_func(id=str(ObjectId()), roles=[Role.CAREGIVER])
    patient = await create_user_func(id=str(ObjectId()), roles=[Role.USER])

    resp = await client.post(
        "/api/v1/caregivers/access-requests/caregiver",
        json={"patientId": str(patient.id)},
        headers=auth_headers(str(caregiver.id)),
    )
    assert resp.status_code == 201
    request_id = resp.json()["id"]

    resp = await client.get(
        "/api/v1/patients/access-requests/incoming",
        headers=auth_headers(str(patient.id)),
    )
    assert resp.status_code == 200
    assert [item["id"] for item in resp.json()] == [request_id]

    resp = await client.post(
        f"/api/v1/caregivers/access-requests/{request_id}/accept",
        headers=auth_headers(str(patient.id)),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "accepted"

    resp = await client.get(
        "/api/v1/caregivers/patients",
        headers=auth_headers(str(caregiver.id)),
    )
    assert resp.status_code == 200
    assert [item["id"] for item in resp.json()] == [str(patient.id)]


@pytest.mark.asyncio
async def test_patient_invite_flow(
    client: AsyncClient, create_user_func
) -> None:
    caregiver = await create_user_func(id=str(ObjectId()), roles=[Role.CAREGIVER])
    patient = await create_user_func(id=str(ObjectId()), roles=[Role.USER])

    resp = await client.post(
        "/api/v1/caregivers/access-requests/patient",
        json={"caregiverId": str(caregiver.id)},
        headers=auth_headers(str(patient.id)),
    )
    assert resp.status_code == 201
    request_id = resp.json()["id"]

    resp = await client.get(
        "/api/v1/caregivers/access-requests/incoming",
        headers=auth_headers(str(caregiver.id)),
    )
    assert resp.status_code == 200
    assert [item["id"] for item in resp.json()] == [request_id]

    resp = await client.post(
        f"/api/v1/caregivers/access-requests/{request_id}/accept",
        headers=auth_headers(str(caregiver.id)),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "accepted"

    resp = await client.get(
        "/api/v1/caregivers/patients",
        headers=auth_headers(str(caregiver.id)),
    )
    assert resp.status_code == 200
    assert [item["id"] for item in resp.json()] == [str(patient.id)]
