import structlog

from app.core import security
from app.modules.users.models import User
from app.modules.users.schemas import UserCreate

log = structlog.get_logger()


class UserService:
    async def get(self, user_id: str) -> User | None:
        user: User | None = await User.get(user_id)
        return user

    async def get_by_email(self, email: str) -> User | None:
        user: User | None = await User.find_one(User.email == email)
        return user

    async def create(self, user_in: UserCreate) -> User:
        log.info(
            "creating_user", email=user_in.email, password_len=len(user_in.password)
        )

        user = User(
            email=user_in.email,
            hashed_password=security.get_password_hash(user_in.password),
            roles=user_in.roles,
            status=user_in.status,
            profile=user_in.profile.model_dump(),
        )
        await user.insert()
        return user
