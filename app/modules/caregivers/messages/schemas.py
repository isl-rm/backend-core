from datetime import datetime
from typing import Optional

from app.shared.schemas import CamelModel


class MessageThreadPreview(CamelModel):
    thread_id: str
    patient_name: str
    last_message: Optional[str] = None
    last_message_at: Optional[datetime] = None
    unread_count: int = 0
