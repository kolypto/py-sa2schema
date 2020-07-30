from typing import Tuple

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.ext.declarative import DeclarativeMeta
from sqlalchemy.orm import sessionmaker


def init_database(url: str, autoflush=True) -> Tuple[Engine, sessionmaker]:
    """ Init database """
    engine = create_engine(url)
    Session = sessionmaker(autocommit=autoflush, autoflush=autoflush, bind=engine)
    return engine, Session


def create_all(engine: Engine, Base: DeclarativeMeta):
    """ Create all tables """
    Base.metadata.create_all(bind=engine)


def drop_all(engine: Engine, Base: DeclarativeMeta):
    """ Drop all tables """
    Base.metadata.drop_all(bind=engine)
