import pytest
from .db import init_database, drop_all, create_all
from .models import Base


@pytest.fixture()
def sqlite_session():
    engine, Session = init_database(url='sqlite://')
    drop_all(engine, Base)
    create_all(engine, Base)

    ssn = Session()
    try:
        yield ssn
    finally:
        ssn.close()

    engine.dispose()
