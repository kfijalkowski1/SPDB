# pdf loader

# poi api caller
import contextlib
import functools
import os
from typing import Generator
from sqlalchemy import URL, Engine, create_engine
from sqlalchemy.orm import sessionmaker, Session
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

def _get_db_url() -> URL:
    return URL.create(
        drivername="postgresql+psycopg2",
        username=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        host=os.environ["POSTGRES_HOST"],
        port=int(os.getenv("POSTGRES_PORT", 5432)),
        database=os.getenv("POSTGRES_DATABASE", "routing")
    )


@functools.lru_cache(maxsize=1)
def _get_engine() -> Engine:
    engine = create_engine(_get_db_url(), echo=True)
    return engine

@contextlib.contextmanager
def session() -> Generator[Session, None, None]:
    engine = _get_engine()
    SessionLocal = sessionmaker(engine, expire_on_commit=False)

    """Get a database session"""
    with SessionLocal() as session:
        yield session
        session.commit()
