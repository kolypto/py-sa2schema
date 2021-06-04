import ast
import sys

import pytest
import sqlalchemy as sa
if sa.__version__ < '1.4.0':
    from sqlalchemy.ext.declarative import declarative_base
else:
    from sqlalchemy.orm import declarative_base

from sa2schema import AttributeType
from sa2schema.to.pydantic import Models
from sa2schema.to.pydantic.stubgen import stubs_for_pydantic
from sa2schema.stubgen import stubs_for_sa_models


PYTHON_LT_39 = sys.version_info < (3, 9)


@pytest.mark.skipif(PYTHON_LT_39, reason='ast.unparse() only available since Python 3.9')
def test_stubgen_sqlalchemy():
    py = ast.unparse(stubs_for_sa_models([User, Article]))
    assert py == '''
from __future__ import annotations
import builtins, datetime, tests.test_stubgen, typing
NoneType = type(None)

class User:
    """ User model """
    id: int = ...
    login: typing.Union[str, NoneType] = ...
    articles: list[tests.test_stubgen.Article] = ...

class Article:
    """ Article model """
    id: int = ...
    user_id: typing.Union[int, NoneType] = ...
    ctime: typing.Union[datetime.datetime, NoneType] = ...
    user: typing.Union[tests.test_stubgen.User, NoneType] = ...
    '''.strip()


@pytest.mark.skipif(PYTHON_LT_39, reason='ast.unparse() only available since Python 3.9')
def test_stubgen_pydantic():
    # Prepare models
    models = Models(__name__, types=AttributeType.ALL, naming='{model}Model')
    models.sa_model(User)
    models.sa_model(Article)

    # Convert
    py = ast.unparse(stubs_for_pydantic(models))
    assert py == '''
from __future__ import annotations
import pydantic
import builtins, datetime, typing
NoneType = type(None)

class UserModel(pydantic.main.BaseModel):
    """ User model """
    id: int = ...
    login: typing.Union[str, NoneType] = ...
    articles: list[ArticleModel] = ...

class ArticleModel(pydantic.main.BaseModel):
    """ Article model """
    id: int = ...
    user_id: typing.Union[int, NoneType] = ...
    ctime: typing.Union[datetime.datetime, NoneType] = ...
    user: typing.Union[UserModel, NoneType] = ...    
'''.strip()



Base = declarative_base()


class User(Base):
    """ User model """
    __tablename__ = 'u'
    id = sa.Column(sa.Integer, primary_key=True)
    login = sa.Column(sa.String)

    articles = sa.orm.relationship(lambda: Article, back_populates='user')

class Article(Base):
    """ Article model """
    __tablename__ = 'a'
    id = sa.Column(sa.Integer, primary_key=True)
    user_id = sa.Column(sa.ForeignKey(User.id))
    ctime = sa.Column(sa.DateTime)

    user = sa.orm.relationship(User, back_populates='articles')

