from datetime import datetime, timezone
from typing import List, Optional

from fastapi import WebSocket

from app.modules.users.models import User
from app.modules.vitals.models import Vital, VitalType
from app.modules.vitals.schemas import (
    DashboardSummary,
    DashboardVitals,
    VitalBulkCreate,
    VitalCreate,
)


class VitalService:
    """Persistence and read layer for vitals, including dashboard shaping and streaming hooks."""

    async def create(self, vital_in: VitalCreate, user: User) -> Vital:
        """Persist a single vital after normalizing its timestamp to UTC seconds."""
        timestamp = self._normalize_timestamp(vital_in.timestamp or datetime.now(timezone.utc))
        vital = Vital(
            type=vital_in.type,
            value=vital_in.value,
            unit=vital_in.unit,
            user=user,
            timestamp=timestamp,
        )
        await vital.insert()
        return vital

    async def process_vital_stream(
        self, vital_in: VitalCreate, user: User, raw_data: str
    ) -> None:
        """
        Process a vital sign received via WebSocket:
        1. Persist it to the database.
        2. Broadcast it to connected consumers.
        """
        # 1. Persist
        await self.create(vital_in, user)

        # 2. Broadcast
        # Ensure we're using the global manager instance for broadcasting
        await vital_manager.broadcast_vital(raw_data)

    async def get_multi(
        self,
        user: User,
        type: Optional[VitalType] = None,
        limit: int = 100,
        skip: int = 0,
    ) -> List[Vital]:
        """Return vitals for a user sorted newest-first with optional type filtering and pagination."""
        query = Vital.find(Vital.user.id == user.id)
        if type:
            query = query.find(Vital.type == type)
        vitals: List[Vital] = (
            await query.sort("-timestamp").skip(skip).limit(limit).to_list()
        )
        return vitals

    async def get_latest(
        self, user: User, type: Optional[VitalType] = None
    ) -> Vital | None:
        """Return the most recent vital for a user, optionally constrained to a type."""
        query = Vital.find(Vital.user.id == user.id)
        if type:
            query = query.find(Vital.type == type)
        return await query.sort("-timestamp").first_or_none()

    async def get_dashboard_summary(self, user: User) -> DashboardSummary:
        """Build dashboard summary fields from the first available vital in each category."""
        # Map dashboard fields to acceptable vital types in priority order
        type_groups: list[tuple[str, list[VitalType]]] = [
            ("ecg", [VitalType.ECG]),
            ("bloodPressure", [VitalType.BLOOD_PRESSURE]),
            ("heartRate", [VitalType.HEART_RATE, VitalType.BPM]),
            ("spo2", [VitalType.SPO2]),
            ("temperatureC", [VitalType.TEMPERATURE]),
            ("respRate", [VitalType.RESP_RATE]),
            ("bloodSugar", [VitalType.BLOOD_SUGAR]),
            ("weightKg", [VitalType.WEIGHT_KG]),
        ]

        vitals_model = DashboardVitals()
        last_updated: datetime | None = None

        for field_name, vital_types in type_groups:
            # Step 1: Pick the first available vital matching the prioritized types
            vital = await self._first_available(user=user, types=vital_types)
            if not vital:
                continue

            timestamp = self._ensure_utc(vital.timestamp)
            setattr(vitals_model, field_name, self._format_dashboard_value(field_name, vital))

            # Step 2: Track the newest timestamp encountered for summary metadata
            if not last_updated or timestamp > last_updated:
                last_updated = timestamp

        status = "empty" if last_updated is None else "ok"
        status_note = "No vitals found" if last_updated is None else "Latest vitals available"

        return DashboardSummary(
            status=status,
            statusNote=status_note,
            lastUpdated=last_updated,
            vitals=vitals_model,
        )

    async def create_bulk(self, bulk_in: VitalBulkCreate, user: User) -> List[Vital]:
        """Insert multiple vitals, reusing a normalized timestamp when one is not provided."""
        vitals: List[Vital] = []
        now = self._normalize_timestamp(datetime.now(timezone.utc))
        for vital_in in bulk_in.vitals:
            timestamp = self._normalize_timestamp(vital_in.timestamp or now)
            # Each Vital uses either its provided timestamp or a shared normalized 'now'
            vitals.append(
                Vital(
                    type=vital_in.type,
                    value=vital_in.value,
                    unit=vital_in.unit,
                    user=user,
                    timestamp=timestamp,
                )
            )

        await Vital.insert_many(vitals)
        vitals.sort(key=lambda v: v.timestamp, reverse=True)
        return vitals

    async def _first_available(
        self, user: User, types: list[VitalType]
    ) -> Vital | None:
        """Return the newest vital for the first matching type in the provided priority list."""
        for vital_type in types:
            vital = await self.get_latest(user=user, type=vital_type)
            if vital:
                return vital
        return None

    def _format_dashboard_value(self, field_name: str, vital: Vital) -> str | float:
        """Normalize dashboard values so pressure stays string-based while others stay numeric."""
        if field_name == "bloodPressure":
            suffix = f" {vital.unit}" if vital.unit else ""
            return f"{vital.value}{suffix}"
        if field_name == "ecg":
            return str(vital.value)
        return vital.value

    def _normalize_timestamp(self, value: datetime) -> datetime:
        """
        Normalize timestamps to second precision and ensure they are timezone-aware in UTC.
        """
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        else:
            value = value.astimezone(timezone.utc)
        return value.replace(microsecond=0)

    def _ensure_utc(self, value: datetime) -> datetime:
        """
        Ensure datetime is timezone-aware in UTC without altering seconds precision.
        """
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class VitalConnectionManager:
    """
    Manages WebSocket connections for real-time vital streaming.
    Separates connections into 'mobile' (producers) and 'frontend' (consumers).
    """

    def __init__(self) -> None:
        self.mobile_connections: List[WebSocket] = []
        self.frontend_connections: List[WebSocket] = []

    async def connect_mobile(self, websocket: WebSocket) -> None:
        """Accept and track a producer connection from mobile."""
        await websocket.accept()
        self.mobile_connections.append(websocket)

    def disconnect_mobile(self, websocket: WebSocket) -> None:
        """Drop a producer connection if it is still tracked."""
        if websocket in self.mobile_connections:
            self.mobile_connections.remove(websocket)

    async def connect_frontend(self, websocket: WebSocket) -> None:
        """Accept and track a consumer connection from the frontend."""
        await websocket.accept()
        self.frontend_connections.append(websocket)

    def disconnect_frontend(self, websocket: WebSocket) -> None:
        """Drop a consumer connection if it is still tracked."""
        if websocket in self.frontend_connections:
            self.frontend_connections.remove(websocket)

    async def broadcast_vital(self, data: str) -> None:
        """
        Broadcasts data received from a mobile producer to all frontend consumers.
        """
        # Iterate over a copy to avoid modification issues during iteration if disconnect happens
        for connection in list(self.frontend_connections):
            try:
                await connection.send_text(data)
            except Exception:
                # If sending fails, assume connection is dead and remove it
                self.disconnect_frontend(connection)


vital_manager = VitalConnectionManager()
