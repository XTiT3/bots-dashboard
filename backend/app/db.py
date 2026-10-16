import datetime as dt
from typing import Optional
from sqlmodel import SQLModel, Field, Session, create_engine
from .config import settings

engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    discord_id: str = Field(index=True, unique=True)
    username: str
    avatar: Optional[str] = None
    access_token: str
    refresh_token: str = ""
    token_expires_at: dt.datetime
    created_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.timezone.utc))

class AuditLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int
    guild_id: str
    bot_id: str
    action: str
    details: str = ""
    created_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.timezone.utc))

def init_db() -> None:
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
