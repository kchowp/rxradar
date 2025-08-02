import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv("DATABASE_URL")
print("DATABASE_URL in db.py:", DATABASE_URL)
print("✅ DATABASE_URL from env:", os.getenv("DATABASE_URL"))


if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set. Please check your environment variables.")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
