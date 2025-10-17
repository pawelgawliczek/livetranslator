from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .settings import settings
from .models import Base

engine = create_engine(settings.LT_DB_URL, pool_size=10, max_overflow=10, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

def get_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def migrate():
    Base.metadata.create_all(engine)
