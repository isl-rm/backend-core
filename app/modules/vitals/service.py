from datetime import datetime
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
    async def create(self, vital_in: VitalCreate, user: User) -> Vital:
        timestamp = self._normalize_timestamp(vital_in.timestamp or datetime.utcnow())
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
        query = Vital.find(Vital.user.id == user.id)
        if type:
            query = query.find(Vital.type == type)
        return await query.sort("-timestamp").first_or_none()

    async def get_dashboard_summary(self, user: User) -> DashboardSummary:
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
            vital = await self._first_available(user=user, types=vital_types)
            if not vital:
                continue

            setattr(vitals_model, field_name, self._format_dashboard_value(field_name, vital))

            if not last_updated or vital.timestamp > last_updated:
                last_updated = vital.timestamp

        status = "empty" if last_updated is None else "ok"
        status_note = "No vitals found" if last_updated is None else "Latest vitals available"

        return DashboardSummary(
            status=status,
            statusNote=status_note,
            lastUpdated=last_updated,
            vitals=vitals_model,
        )

    async def create_bulk(self, bulk_in: VitalBulkCreate, user: User) -> List[Vital]:
        vitals: List[Vital] = []
        now = self._normalize_timestamp(datetime.utcnow())
        for vital_in in bulk_in.vitals:
            timestamp = self._normalize_timestamp(vital_in.timestamp or now)
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
        for vital_type in types:
            vital = await self.get_latest(user=user, type=vital_type)
            if vital:
                return vital
        return None

    def _format_dashboard_value(self, field_name: str, vital: Vital) -> str | float:
        if field_name == "bloodPressure":
            suffix = f" {vital.unit}" if vital.unit else ""
            return f"{vital.value}{suffix}"
        if field_name == "ecg":
            return str(vital.value)
        return vital.value

    def _normalize_timestamp(self, value: datetime) -> datetime:
        # Force second-level precision (strip microseconds)
        return value.replace(microsecond=0)


class VitalConnectionManager:
    """
    Manages WebSocket connections for real-time vital streaming.
    Separates connections into 'mobile' (producers) and 'frontend' (consumers).
    """

    def __init__(self) -> None:
        self.mobile_connections: List[WebSocket] = []
        self.frontend_connections: List[WebSocket] = []

    async def connect_mobile(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.mobile_connections.append(websocket)

    def disconnect_mobile(self, websocket: WebSocket) -> None:
        if websocket in self.mobile_connections:
            self.mobile_connections.remove(websocket)

    async def connect_frontend(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.frontend_connections.append(websocket)

    def disconnect_frontend(self, websocket: WebSocket) -> None:
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
