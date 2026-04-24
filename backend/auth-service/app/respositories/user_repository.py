from sqlalchemy.orm import Session
from app.models import User, AuthProvider


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_email(self, email: str):
        return self.db.query(User).filter(User.email == email).first()


    def get_by_provider(self, provider: str, provider_id: str):
        return (
            self.db.query(User)
            .join(AuthProvider)
            .filter(
                AuthProvider.provider == provider,
                AuthProvider.provider_id == provider_id
            )
            .first()
        )

    def create(self, user_data: dict):
        user = User(**user_data)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update(self, user: User):
        self.db.commit()
        self.db.refresh(user)
        return user