from datetime import datetime
from typing import List, Optional

from app.modules.users.models import User
from app.modules.vitals.models import Vital, VitalType
from app.modules.vitals.schemas import VitalCreate


class VitalService:
    async def create(self, vital_in: VitalCreate, user: User) -> Vital:
        vital = Vital(
            type=vital_in.type,
            value=vital_in.value,
            unit=vital_in.unit,
            user=user,
            timestamp=vital_in.timestamp or datetime.utcnow(),
        )
        await vital.insert()
        return vital

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
