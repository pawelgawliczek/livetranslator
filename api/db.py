from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from .settings import settings

class Base(DeclarativeBase): pass

engine = create_engine(settings.LT_DB_URL, pool_pre_ping=True, pool_size=5, max_overflow=10, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

def migrate():
    from .models import User, Room, Device, Event, RoomParticipant, RoomCost  # noqa
    Base.metadata.create_all(engine)
