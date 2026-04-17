import os
from sqlmodel import SQLModel, create_engine, Session

# Database Config
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")

connect_args = {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)

def get_session():
    with Session(engine) as session:
        yield session

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)
