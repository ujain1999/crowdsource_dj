from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from config import settings

engine = create_engine(settings.DATABASE_URL, echo=settings.DEBUG)
engine = create_engine(settings.DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
