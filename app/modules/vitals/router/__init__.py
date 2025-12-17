"""Compose vitals HTTP and WebSocket routers."""

from fastapi import APIRouter
from jose import jwt

from app.modules.vitals.service import vital_manager
from .http import (
    create_vital,
    create_vitals_bulk,
    get_vitals_query_params,
    read_dashboard_summary,
    read_latest_vital,
    read_vital_series,
    read_vitals,
    router as http_router,
)
from .ws_frontend import router as ws_frontend_router
from .ws_mobile import (
    _authenticate_mobile_websocket,
    _build_ecg_broadcast_payload,
    _handle_ecg_payload,
    _is_ecg_payload,
    _process_mobile_message,
    router as ws_mobile_router,
)

router = APIRouter()
router.include_router(http_router)
router.include_router(ws_mobile_router)
router.include_router(ws_frontend_router)

# Re-export handlers and helpers for existing tests and consumers
__all__ = [
    "router",
    "create_vital",
    "create_vitals_bulk",
    "get_vitals_query_params",
    "read_dashboard_summary",
    "read_latest_vital",
    "read_vital_series",
    "read_vitals",
    "_authenticate_mobile_websocket",
    "_build_ecg_broadcast_payload",
    "_handle_ecg_payload",
    "_is_ecg_payload",
    "_process_mobile_message",
    "vital_manager",
    "jwt",
]
