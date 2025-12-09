from app.core import security
from app.modules.users.models import User
from app.modules.users.schemas import UserCreate


class UserService:
    async def get(self, user_id: str) -> User | None:
        user: User | None = await User.get(user_id)
        return user

    async def get_by_email(self, email: str) -> User | None:
        user: User | None = await User.find_one(User.email == email)
        return user

    async def create(self, user_in: UserCreate) -> User:
        user = User(
            email=user_in.email,
            hashed_password=security.get_password_hash(user_in.password),
            full_name=user_in.full_name,
            is_active=user_in.is_active,
        )
        await user.insert()
        return user
