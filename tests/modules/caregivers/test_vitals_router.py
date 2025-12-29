"""Tests for caregiver vitals endpoints."""

from typing import Any

import pytest
from httpx import AsyncClient

from app.core import security
from app.modules.caregivers.patients.models import CaregiverPatientAccess
from app.modules.users.models import User
from app.modules.vitals.models import Vital, VitalType
from app.shared.constants import Role


@pytest.fixture
async def caregiver_user(create_user_func: Any) -> User:
    """Create a caregiver user for testing."""
    return await create_user_func(
        email="caregiver@example.com",
        roles=[Role.CAREGIVER],
    )


@pytest.fixture
async def patient_user(create_user_func: Any) -> User:
    """Create a patient user for testing."""
    return await create_user_func(
        email="patient@example.com",
        roles=[Role.USER],
    )


@pytest.fixture
def caregiver_token(caregiver_user: User) -> str:
    """Generate an access token for the caregiver user."""
    return security.create_access_token(subject=str(caregiver_user.id))


@pytest.fixture
def patient_token(patient_user: User) -> str:
    """Generate an access token for the patient user."""
    return security.create_access_token(subject=str(patient_user.id))


@pytest.mark.asyncio
async def test_caregiver_can_view_patient_dashboard(
    client: AsyncClient,
    caregiver_user: User,
    patient_user: User,
    caregiver_token: str,
) -> None:
    """Test that a caregiver can view their patient's dashboard summary."""
    # Grant caregiver access to patient
    access = CaregiverPatientAccess(
        caregiver_id=str(caregiver_user.id),
        patient_id=str(patient_user.id),
        active=True,
    )
    await access.insert()

    # Create some vitals for the patient
    vitals = [
        Vital(
            type=VitalType.HEART_RATE,
            value=75.0,
            unit="bpm",
            user=patient_user,
        ),
        Vital(
            type=VitalType.BLOOD_PRESSURE,
            value="120/80",
            unit="mmHg",
            user=patient_user,
        ),
        Vital(
            type=VitalType.SPO2,
            value=98.0,
            unit="%",
            user=patient_user,
        ),
    ]
    await Vital.insert_many(vitals)

    # Request patient dashboard as caregiver
    response = await client.get(
        f"/api/v1/caregivers/patients/{patient_user.id}/dashboard",
        headers={"Authorization": f"Bearer {caregiver_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["vitals"]["heartRate"] == 75.0
    assert data["vitals"]["bloodPressure"] == "120/80 mmHg"
    assert data["vitals"]["spo2"] == 98.0


@pytest.mark.asyncio
async def test_caregiver_cannot_view_unauthorized_patient_dashboard(
    client: AsyncClient,
    caregiver_user: User,
    patient_user: User,
    caregiver_token: str,
) -> None:
    """Test that a caregiver cannot view a patient's dashboard without access."""
    # Do NOT grant access

    # Attempt to request patient dashboard as caregiver
    response = await client.get(
        f"/api/v1/caregivers/patients/{patient_user.id}/dashboard",
        headers={"Authorization": f"Bearer {caregiver_token}"},
    )

    assert response.status_code == 403
    assert "do not have access" in response.json()["detail"]


@pytest.mark.asyncio
async def test_patient_cannot_view_dashboard_via_caregiver_endpoint(
    client: AsyncClient,
    patient_user: User,
    patient_token: str,
) -> None:
    """Test that a patient cannot use the caregiver endpoint."""
    response = await client.get(
        f"/api/v1/caregivers/patients/{patient_user.id}/dashboard",
        headers={"Authorization": f"Bearer {patient_token}"},
    )

    # Should be forbidden since patient doesn't have CAREGIVER role
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_caregiver_dashboard_returns_empty_when_no_vitals(
    client: AsyncClient,
    caregiver_user: User,
    patient_user: User,
    caregiver_token: str,
) -> None:
    """Test that dashboard returns empty status when patient has no vitals."""
    # Grant caregiver access to patient
    access = CaregiverPatientAccess(
        caregiver_id=str(caregiver_user.id),
        patient_id=str(patient_user.id),
        active=True,
    )
    await access.insert()

    # Request patient dashboard as caregiver (no vitals created)
    response = await client.get(
        f"/api/v1/caregivers/patients/{patient_user.id}/dashboard",
        headers={"Authorization": f"Bearer {caregiver_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "empty"
    assert data["statusNote"] == "No vitals found"
    assert data["lastUpdated"] is None

