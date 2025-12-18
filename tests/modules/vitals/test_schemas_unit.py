from datetime import datetime, timezone

import pytest

from app.modules.vitals.models import VitalType
from app.modules.vitals.schemas import (
    BloodPressureReading,
    EcgStreamPayload,
    VitalBulkCreate,
    VitalCreate,
)


def test_vital_create_converts_epoch_timestamp() -> None:
    ts = 1_700_000_000

    model = VitalCreate(type=VitalType.BPM, value=70, unit="bpm", timestamp=ts)

    assert model.timestamp == datetime.fromtimestamp(ts, tz=timezone.utc)


def test_vital_create_accepts_structured_blood_pressure() -> None:
    model = VitalCreate(
        type=VitalType.BLOOD_PRESSURE,
        blood_pressure=BloodPressureReading(systolic=118, diastolic=76),
        unit="mmHg",
    )

    assert model.value == "118/76"
    assert model.blood_pressure.as_string() == "118/76"


def test_vital_create_parses_slash_separated_blood_pressure() -> None:
    model = VitalCreate(
        type=VitalType.BLOOD_PRESSURE,
        value="120/80",
        unit="mmHg",
    )

    assert model.value == "120/80"
    assert model.blood_pressure is not None
    assert model.blood_pressure.systolic == 120
    assert model.blood_pressure.diastolic == 80


def test_vital_bulk_create_requires_vitals() -> None:
    with pytest.raises(ValueError, match="vitals list cannot be empty"):
        VitalBulkCreate(vitals=[])


def test_ecg_stream_payload_lifts_nested_payload_and_prefers_top_level() -> None:
    payload = {
        "payload": {"bpm": 60, "sampleRate": 300, "timestamp": 1_700_000_100},
        "bpm": 75,  # top-level value should win
    }

    ecg = EcgStreamPayload.model_validate(payload)

    assert ecg.bpm == 75
    assert ecg.sample_rate == 300
    assert ecg.timestamp == datetime.fromtimestamp(1_700_000_100, tz=timezone.utc)


def test_ecg_stream_payload_requires_data() -> None:
    with pytest.raises(ValueError, match="ECG payload must include bpm or samples"):
        EcgStreamPayload.model_validate({})


@pytest.mark.parametrize(
    "data, message",
    [
        ({"samples": [], "bpm": 70}, "samples cannot be empty"),
        ({"bpm": 70, "sampleRate": 0}, "sampleRate must be positive"),
    ],
)
def test_ecg_stream_payload_validation_errors(data: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        EcgStreamPayload.model_validate(data)
