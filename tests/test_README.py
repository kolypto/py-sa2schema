""" Test the code from README """

# models.py
import pytest
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Session
import pydantic as v


# SqlAlchemy models
Base = declarative_base()


class User(Base):
    __tablename__ = 'users'

    # This column will automatically be picked up as `id: int`
    id = Column(Integer, primary_key=True)

    # Will become `login: Optional[str]`
    login = Column(String, nullable=True)
    password = Column(String, nullable=True)

    # An SqlAlchemy column with extra validation in Pydantic
    # The annotation is ignored by SqlAlchemy, but is picked up by Pydantic
    email: v.EmailStr = Column(String, nullable=True)


class Article(Base):
    __tablename__ = 'articles'

    # Some columns
    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)

    # A relationship
    author_id = Column(ForeignKey(User.id))
    author = relationship(User, backref='articles')



class models:
    """ Namespace that imitates a module """
    User = User
    Article = Article





# schemas.py
from typing import Optional
from datetime import datetime

from sa2schema.to.pydantic import sa_model  # SqlAlchemy -> Pydantic converter




@pytest.fixture()
def sqlite_session(Base=Base):  # a shameful copy-paste from ./conftest.py because I can't give arguments to a fixture :(
    from .db import init_database, drop_all, create_all
    engine, Session = init_database(url='sqlite://')

    if Base:
        drop_all(engine, Base)
        create_all(engine, Base)

    ssn = Session()
    try:
        yield ssn
    finally:
        ssn.close()

    engine.dispose()


def test_example_with_columns(sqlite_session: Session):
    class schemas:  # fake module
        # The User as it is in the database, 100% following models.User
        UserInDb = sa_model(models.User)

        # A partial User: all fields are Optional[].
        # Useful for updates, or for partial responses where not all fields are loaded
        UserPartial = sa_model(models.User, make_optional=True)

        # A User for updates: only fields that are writable are included
        # An additional field, `id`, is excluded, because API users won't modify primary keys
        UserWritable = sa_model(models.User, only_writable=True, exclude=('id',))

        # A User model with overrides
        # For output, we don't want the password to be exposed, so its excluded
        class UserOutput(sa_model(models.User, exclude=('password',))):
            # Some further fields that are dynamically calculated
            password_set: bool
            password_expires: Optional[datetime]

    # === Use

    # Create a user
    ssn = sqlite_session
    ssn.add(models.User(
        id=1,
        login='kolypto',
        email='kolypto@example.com',
    ))
    ssn.flush()

    # Load from the DB and convert
    user: models.User = ssn.query(models.User).first()  # load
    pd_user = schemas.UserInDb.from_orm(user)  # -> Pydantic
    user_dict = pd_user.dict()  # -> dict
    assert user_dict == {
        'id': 1,
        'login': 'kolypto',
        'email': 'kolypto@example.com',
        'password': None,
    }

    # Load from the user input and update the `user` object
    pd_user = schemas.UserPartial(email='user@example.com')
    for name, value in pd_user.dict(skip_defaults=True).items():
        # Update every attribute of an SqlAlchemy model `user`
        setattr(user, name, value)

    assert user.email == 'user@example.com'  # updated


def test_example_with_columns(sqlite_session: Session):
    class schemas:  # namespace
        from sa2schema.to.pydantic import sa_models, AttributeType

        # A _pydantic_names for related models
        # They have to be put "in a box" so that they can find each other
        models_in_db = sa_models(__name__,
                                 # Naming convention for our models: "...InDb"
                                 # This is required to resolve forward references in Python annotations
                                 naming='{model}InDb',
                                 # `types` specifies which attributes do you want to include.
                                 # We include relationships explicitly, becase by default, they're excluded.
                                 types=AttributeType.COLUMN | AttributeType.RELATIONSHIP
                                 )

        # Put our models into the namespace
        # Every SqlAlchemy model gets converted into a Pydantic model.
        # They link to one another through a common namespace
        UserInDb = models_in_db.add(models.User)
        ArticleInDb = models_in_db.add(models.Article)

        # Unfortunately, this is required to resolve forward references
        models_in_db.update_forward_refs()

    # === Use

    # JSON received from an API user
    user_input = {
        'id': 1,
        'login': 'kolypto',
        # values for the relationship
        'articles': [
            {'id': 1, 'title': 'SqlAlchemy'},
            {'id': 2, 'title': 'Pydantic'},
        ]
    }

    # Validate the data through Pydantic
    pydantic_user = schemas.UserInDb(**user_input)

    # === from DB

    ssn = sqlite_session
    ssn.add(models.User(
        id=1,
        login='kolypto',
        articles=[
            models.Article(id=1, title='SqlAlchemy'),
        ]
    ))
    ssn.flush()

    # Load a user from DB
    user = ssn.query(models.User).first()

    # Convert to Pydantic
    pydantic_user = schemas.UserInDb.from_orm(user)

    # To JSON
    assert pydantic_user.dict() == {
        'id': 1,
        'login': 'kolypto',
        'password': None,
        'email': None,
        # Relationship is loaded
        'articles': [
            {
                'id': 1,
                'title': 'SqlAlchemy',
                'author_id': 1,
                # Circular reference replaced with None to prevent infinite recursion
                'author': None,
            }
        ]
    }


def test_avoiding_too_many_sql_queries(sqlite_session: Session):
    class schemas:
        from sa2schema.to.pydantic import sa_models, AttributeType, SALoadedModel

        partial = sa_models(__name__,
                            naming='{model}Partial',
                            # Include columns and relationships
                            types=AttributeType.COLUMN | AttributeType.RELATIONSHIP,
                            # Create a "partial model": make every field Optional[]
                            make_optional=True,
                            # Use another base class that will only get loaded attributes
                            Base=SALoadedModel
                            )

        partial.add(models.User)
        partial.add(models.Article)
        partial.update_forward_refs()

    # Prepare

    ssn = sqlite_session
    ssn.add(models.User(
        id=1,
        login='kolypto',
        articles=[
            models.Article(id=1, title='SqlAlchemy'),
        ]
    ))
    ssn.flush()

    # === Load

    # Load a user from DB
    user = ssn.query(models.User).get(1)

    # Convert it to a Pydantic model
    # Note that we use `partial` as a namespace and refer to a model by name
    pd_user: BaseModel = schemas.partial.User.from_orm(user)
    assert pd_user.dict() == {
        # Loaded fields are reported
        'id': 1,
        'login': 'kolypto',
        'email': None, 'password': None,
        # Unloaded relationship is reported as a `None`
        'articles': None,
    }

    # Use a feature of Pydantic to remove those `None`s if you like
    assert pd_user.dict(exclude_none=True) == {
        'id': 1,
        'login': 'kolypto',
        # 'articles' isn't here anymore
    }
