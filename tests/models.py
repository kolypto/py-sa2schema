""" Models for testing """
from enum import Enum
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.hybrid import hybrid_property, hybrid_method
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm.collections import attribute_mapped_collection, mapped_collection

from sa2schema import loads_attributes, loads_attributes_readcode

Base = declarative_base()


class EnumType(Enum):
    """ Enumeration (used in SqlAlchemy model) """
    a = 1
    b = 2


class Point:
    """ Point: a composite type using two fields """
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __composite_values__(self):
        return self.x, self.y


# A class with every conceivable attribute type

class User(Base):
    """ Model comment """
    __tablename__ = 'users'  # sqlalchemy wants it

    _ignored = sa.Column(sa.String)

    # Annotated column: type will be taken from the annotation
    # In no other case an annotated column will be tested
    annotated_int: int = sa.Column(sa.String, primary_key=True)

    # Column(Integer): type will be taken from the column type
    int = sa.Column(sa.Integer)
    # Interesting special type that depends on another
    enum = sa.Column(sa.Enum(EnumType))
    # Optional and required columns
    optional = sa.Column(sa.String, nullable=True)
    required = sa.Column(sa.String, nullable=False)
    # Field with a default
    default = sa.Column(sa.String, nullable=False, default='value')
    # Documented field
    documented = sa.Column(sa.String, doc="Some descriptive text")
    # JSON field, as_mutable()
    # NOTE: cannot call it just `json` because that's Pydantic's reserved method
    json_attr = sa.Column(MutableDict.as_mutable(sa.JSON))

    # An untyped property becomes `Any`
    @property
    def property_without_type(self):
        return None

    # A typed property: type taken from the annotation

    @property
    def property_typed(self) -> str:
        return 'b'

    @property
    @loads_attributes_readcode()  # the only property that knows what it loads
    def property_documented(self):
        """ Documented property """
        return self.documented

    @property
    def property_nullable(self) -> Optional[str]:
        return 'o'

    # A writable typed property

    @property
    def property_writable(self) -> str:
        return 'a'

    @property_writable.setter
    def property_writable(self, v='default'):
        pass

    # A hybrid property: same behavior as @property

    @hybrid_property
    def hybrid_property_typed(self) -> str:
        return 'c'

    @hybrid_property
    def hybrid_property_writable(self) -> str:
        pass

    @hybrid_property_writable.setter
    def hybrid_property_writable(self, v='default'):
        pass

    # A hybrid method

    @hybrid_method
    def hybrid_method_attr(self, a: int, b: int):
        return False

    # Column property: a selectable using multiple columns
    expression = sa.orm.column_property(int + annotated_int)

    # Composite type: uses two columns
    point = sa.orm.composite(Point, int, annotated_int)

    # Synonym
    synonym = sa.orm.synonym('point')

    # Relationship
    articles_list = sa.orm.relationship(lambda: Article, back_populates='user')
    articles_set = sa.orm.relationship(lambda: Article, collection_class=set, viewonly=True)
    articles_dict_attr = sa.orm.relationship(lambda: Article, collection_class=attribute_mapped_collection('id'))
    articles_dict_keyfun = sa.orm.relationship(lambda: Article, collection_class=mapped_collection(lambda note: note.id + 1000))

    # Association proxy
    article_titles = association_proxy(
        'articles_list',
        'title'
    )
    article_authors = association_proxy(
        'articles_list',
        'user',
    )

    # Dynamic loader
    articles_q = sa.orm.dynamic_loader(lambda: Article)

# A simple model that relates to User

class Article(Base):
    __tablename__ = 'articles'

    id = sa.Column(sa.Integer, primary_key=True)
    user_id = sa.Column(sa.ForeignKey(User.annotated_int))
    title = sa.Column(sa.String)

    user = sa.orm.relationship(User, back_populates='articles_list')

# A separate model with required & default fields to test validation

class Number(Base):
    __tablename__ = 'animals'

    id = sa.Column(sa.Integer, primary_key=True)

    # nullable, no default
    n = sa.Column(sa.Integer, nullable=True)
    # nullable, default
    nd1 = sa.Column(sa.Integer, nullable=True, default=100)
    nd2 = sa.Column(sa.Integer, nullable=True, default=lambda: 100)
    nd3 = sa.Column(sa.Integer, nullable=True, default=select([1]))
    # not nullable, default
    d1 = sa.Column(sa.Integer, nullable=False, default=100)
    d2 = sa.Column(sa.Integer, nullable=False, default=lambda: 100)
    d3 = sa.Column(sa.Integer, nullable=False, default=select([1]))

# region: Table Inheritance examples

# Joined Table Inheritance

class JTI_Company(Base):
    __tablename__ = 'jti_company'
    id = sa.Column(sa.Integer, primary_key=True)
    name = sa.Column(sa.String(50))
    employees = sa.orm.relationship(lambda: JTI_Employee, back_populates="company")


class JTI_Employee(Base):
    __tablename__ = 'jti_employee'
    id = sa.Column(sa.Integer, primary_key=True)
    name = sa.Column(sa.String(50))
    type = sa.Column(sa.String(50))

    company_id = sa.Column(sa.ForeignKey(JTI_Company.id))
    company = sa.orm.relationship(lambda: JTI_Company, back_populates="employees")

    __mapper_args__ = {
        'polymorphic_identity': 'employee',
        'polymorphic_on': type
    }


class JTI_Engineer(JTI_Employee):
    __tablename__ = 'jti_engineer'
    id = sa.Column(sa.Integer, sa.ForeignKey(JTI_Employee.id), primary_key=True)
    engineer_name = sa.Column(sa.String(30))

    __mapper_args__ = {
        'polymorphic_identity': 'engineer',
    }


# Single Table Inheritance

class STI_Company(Base):
    __tablename__ = 'sti_company'
    id = sa.Column(sa.Integer, primary_key=True)
    name = sa.Column(sa.String(50))

    managers = sa.orm.relationship("STI_Manager", back_populates="company")

class STI_Employee(Base):
    __tablename__ = 'sti_employee'
    id = sa.Column(sa.Integer, primary_key=True)
    name = sa.Column(sa.String(50))
    type = sa.Column(sa.String(50))

    __mapper_args__ = {
        'polymorphic_identity': 'employee',
        'polymorphic_on': type
    }


class STI_Manager(STI_Employee):
    manager_data = sa.Column(sa.String(50))

    company_id = sa.Column(sa.ForeignKey('sti_company.id'))
    company = sa.orm.relationship("STI_Company", back_populates="managers")

    __mapper_args__ = {
        'polymorphic_identity': 'manager'
    }

class STI_Engineer(STI_Employee):
    engineer_info = sa.Column(sa.String(50))

    __mapper_args__ = {
        'polymorphic_identity': 'engineer'
    }

# Concrete Table Inheritance
# Perhaps, some other day

# endregion
