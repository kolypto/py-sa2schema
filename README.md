[![Tests](https://github.com/kolypto/py-sa2schema/workflows/Tests/badge.svg)](/kolypto/py-sa2schema/actions)
[![Pythons](https://img.shields.io/badge/python-3.7%E2%80%933.9-blue.svg)](noxfile.py)

🔴🔴🔴 Project Discontinued 🔴🔴🔴
===================================

NOTE: this project was EXPERIMENTAL and is not DISCONTINUED.


Sqlalchemy model to Pydantic model converter
============================================

*sa2schema* is an SqlAlchemy-to-Pydantic bridge, possibly supporting other schema in the future.

Pydantic Converter
------------------

The `sa2schema.to.pydantic` package lets you convert your SqlAlchemy models into Pydantic models.

> $ pip install sa2schema
> ... 😊

### Example with Columns

Let's start with a basic example: a `User` model that's going to become the source of truth 
for a Pydantic model:

```python
# models.py
from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
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
```

Having such a definition, let's create several Pydantic models from it:

```python
# schemas.py
from typing import Optional
from datetime import datetime

from . import models  # your models file
from sa2schema.to.pydantic import sa_model  # SqlAlchemy -> Pydantic converter

# The User as it is in the database, 100% following models.User
UserInDb = sa_model(models.User)

# A partial User: all fields are Optional[].
# Useful for updates, or for partial responses where not all fields are loaded
UserPartial = sa_model(models.User, make_optional=True)

# A User for updates: only fields that are writable are included, and all of them are made Optional[]
# An additional field, `id`, is excluded, because API users won't modify primary keys
# Useful for overwrites
UserWritable = sa_model(models.User, only_writable=True, make_optional=True, exclude=('id',))

# A User model with overrides
# For output, we don't want the password to be exposed, so its excluded
class UserOutput(sa_model(models.User, exclude=('password',))):
    # Some further fields that are dynamically calculated
    password_set: bool
    password_expires: Optional[datetime]
```

You can now use every model as a Pydantic model:

```python
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
```

### Example with relationships

`sa_model()` also supports relationships and parsin of nested models and collections!
It reads your relationships and accurately sets up Pydantic fields.

Have a look:

```python
# models.py
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

class User(Base):
    ...

class Article(Base):
    __tablename__ = 'articles'

    # Some columns
    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)

    # A relationship
    author_id = Column(ForeignKey(User.id))
    author = relationship(User, backref='articles')
```

now let's make Pydantic models from it:

```python
# schemas.py

from sa2schema.to.pydantic import Models, AttributeType

# A _pydantic_names for related models
# They have to be put "in a box" so that they can find each other
models_in_db = Models(__name__,
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
UserInDb = models_in_db.sa_model(models.User)
ArticleInDb = models_in_db.sa_model(models.Article)

# Unfortunately, this is required to resolve forward references
models_in_db.update_forward_refs()
```

and use it with some real-world data:

```python

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
```

or it can go the other way around:

```python
# Load a user from DB
user = ssn.query(models.User).first()

# Convert to Pydantic
pydantic_user = schemas.UserInDb.from_orm(user)

# To JSON
pydantic_user.dict() # -> 
{
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
```

### Avoiding too many SQL queries
In the preceding example, the `from_orm()` method loaded every attribute from the SqlAlchemy model.
This default behavior is harmful because:

* It will load every unloaded column
* This may result in hundreds of SQL queries ([the N+1 problem](https://github.com/kolypto/py-nplus1loader))
* It will load every relationship
* Loading will go deeper, as far as your models are linked
* Too much data is sent to the client
* Too much load on the DB
* Possible exposure of sensitive data

Instead, it is advised that you use another base class for Pydantic models: `SALoadedModel`.
It will *only touch attributes that are loaded*. Unloaded attributes will be reported as `None`.

Let's create some partial models:

```python
from sa2schema.to.pydantic import Models, AttributeType, SALoadedModel

partial = Models(__name__, naming='{model}Partial',
                 # Include columns and relationships
                 types=AttributeType.COLUMN | AttributeType.RELATIONSHIP,
                 # Create a "partial model": make every field Optional[]
                 make_optional=True,
                 # Use another base class that will only get loaded attributes
                 Base=SALoadedModel
                 )

partial.sa_model(models.User)
partial.sa_model(models.Article)
partial.update_forward_refs()
```

Now, load a User from the database. See how it looks like:

```python
# Load a user from DB
user = ssn.query(models.User).get(1)

# Convert it to a Pydantic model
# Note that we use `partial` as a namespace and refer to a model by name
pd_user = schemas.partial.User.from_orm(user)
pd_user.dict()  # -> 
{
    # Loaded fields are reported
    'id': 1,
    'login': 'kolypto',
    'email': None, 'password': None,
    # Unloaded relationship is reported as a `None`
    'articles': None,
}

# Use a feature of Pydantic to remove those `None`s if you like
pd_user.dict(exclude_none=True) # -> 
{
    'id': 1,
    'login': 'kolypto',
    # 'articles' isn't here anymore
}
```
