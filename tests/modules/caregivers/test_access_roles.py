import pytest
from bson import ObjectId
from httpx import AsyncClient

from app.shared.constants import Role
from tests.modules.caregivers.helpers import auth_headers


@pytest.mark.asyncio
async def test_access_endpoints_enforce_roles(
    client: AsyncClient, create_user_func
) -> None:
    caregiver = await create_user_func(id=str(ObjectId()), roles=[Role.CAREGIVER])
    patient = await create_user_func(id=str(ObjectId()), roles=[Role.USER])

    resp = await client.get(
        "/api/v1/caregivers/access-requests/incoming",
        headers=auth_headers(str(patient.id)),
    )
    assert resp.status_code == 403

    resp = await client.get(
        "/api/v1/patients/access-requests/incoming",
        headers=auth_headers(str(caregiver.id)),
    )
    assert resp.status_code == 403

    resp = await client.get(
        "/api/v1/caregivers/messages",
        headers=auth_headers(str(patient.id)),
    )
    assert resp.status_code == 403

    resp = await client.get(
        "/api/v1/caregivers/messages",
        headers=auth_headers(str(caregiver.id)),
    )
    assert resp.status_code == 200
    assert resp.json() == []
