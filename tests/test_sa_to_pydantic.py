from typing import Any, Dict, Type

import pytest
from pydantic import BaseModel, ValidationError

from sa2schema import AttributeType, sa2

from .models import User, Article, EnumType
from .models import JTI_Employee, JTI_Engineer
from .models import STI_Employee, STI_Manager, STI_Engineer


def test_sa_model_User_columns():
    """ User: COLUMN """
    # Test User: only columns
    pd_User = sa2.pydantic.sa_model(User, types=AttributeType.COLUMN, exclude=('int',))
    assert schema_attrs(pd_User) == {
       'annotated_int': {'type': int, 'default': None, 'required': True},  # override from annotation!
        # note: `type` is always unwrappe by Pydantic. There never is `Optional[]` around it
       'default': {'type': str, 'default': 'value', 'required': False},  # default value is here
       'documented': {'type': str, 'default': None, 'required': False},
       'enum': {'type': EnumType, 'default': None, 'required': False},
       # 'int': {'type': int, 'default': None, 'required': False},  # excluded
       'json_attr': {'type': dict, 'default': None, 'required': False},
       'optional': {'type': str, 'default': None, 'required': False},
       'required': {'type': str, 'default': None, 'required': True}
    }

    # Invalid users
    try:
        user = pd_User()
    except ValidationError as e:
        assert e.errors() == [
            # Both required fields are correctly reported missing
            {'loc': ('annotated_int',), 'msg': 'field required', 'type': 'value_error.missing'},
            {'loc': ('required',), 'msg': 'field required', 'type': 'value_error.missing'},
        ]

    # Valid user
    user = pd_User(annotated_int='1', required=777)
    assert user.annotated_int == 1  # '1' converted to 1
    assert user.default == 'value'  # default's here
    assert user.optional is None  # nullable got it's default
    assert user.required == '777'  # required field is here; converted to string


def test_sa_model_User_properties():
    """ User: PROPERTY """
    # Test User: @property
    pd_User = sa2.pydantic.sa_model(User, types=AttributeType.PROPERTY_RW)
    assert schema_attrs(pd_User) == {
        'property_without_type': {'type': Any, 'default': None, 'required': False},  # nullable => not required
        'property_typed': {'type': str, 'default': None, 'required': True},  # not nullable => required
        'property_documented': {'type': Any, 'default': None, 'required': False},
        'property_nullable': {'type': str, 'default': None, 'required': False},
        'property_writable': {'type': str, 'default': 'default', 'required': False},  # has a default. Not required.
    }

    # Test User: only_readable
    pd_User = sa2.pydantic.sa_model(User, types=AttributeType.PROPERTY_RW, only_readable=True)
    assert set(schema_attrs(pd_User)) == {
        'property_without_type', 'property_typed', 'property_documented', 'property_nullable', 'property_writable',
    }

    # Test User: only_writable
    pd_User = sa2.pydantic.sa_model(User, types=AttributeType.PROPERTY_RW, only_writable=True)
    assert set(schema_attrs(pd_User)) == {
        'property_writable',
    }

    # Use it
    user = pd_User(property_writable=1)
    assert user.property_writable == '1'

    # Test User: @property, `can_omit_nullable=False`
    # NOTE: test disabled, because useless
    # pd_User = sa2.pydantic.sa_model(User, types=AttributeType.PROPERTY_RW, can_omit_nullable=False)  # Only columns
    # assert {field.alias: field.required for field in pd_User.__fields__.values()} == {
    #     'property_without_type': True,  # nullable => required
    #     'property_typed': True,
    #     'property_documented': True,  # nullable => required
    #     'property_nullable': True,  # nullable => required
    #     'property_writable': False,  # has a default => not required
    # }


def test_sa_model_User_hybrid_properties():
    """ User: HYBRID_PROPERTY """
    # Test User: @hybrid_property
    pd_User = sa2.pydantic.sa_model(User, types=AttributeType.HYBRID_PROPERTY_RW)
    assert schema_attrs(pd_User) == {
        'hybrid_property_typed': {'type': str, 'default': None, 'required': True},
        'hybrid_property_writable': {'type': str, 'default': 'default', 'required': False},  # default value set
    }


def test_sa_model_User_exotic():
    """ User: EXPRESSION, HYBRID_METHOD """
    # Test User: exotic types
    pd_User = sa2.pydantic.sa_model(User, types=AttributeType.EXPRESSION | AttributeType.HYBRID_METHOD)
    assert schema_attrs(pd_User) == {
        'expression': {'type': int, 'default': None, 'required': False},
        'hybrid_method_attr': {'type': Any, 'default': None, 'required': False},
    }


def test_inheritance_JTI_Employee():
    """ Test Joined Table Inheritance models """
    pd_JTI_Employee = sa2.pydantic.sa_model(JTI_Employee)
    assert issubclass(pd_JTI_Employee, BaseModel)
    assert set(schema_attrs(pd_JTI_Employee)) == {
        'id', 'name', 'type', 'company_id',
    }

    pd_JTI_Engineer = sa2.pydantic.sa_model(JTI_Engineer)
    assert issubclass(pd_JTI_Engineer, BaseModel)  # wrong inheritance because not set explicitly
    assert set(schema_attrs(pd_JTI_Engineer)) == {
        # inherited
        'id', 'name', 'type', 'company_id',
        # self
        'engineer_name',
    }

    # let's do it right
    pd_JTI_Engineer = sa2.pydantic.sa_model(JTI_Engineer, Parent=pd_JTI_Employee)
    assert issubclass(pd_JTI_Engineer, pd_JTI_Employee)  # correct inheritance

    # use it
    engineer = pd_JTI_Engineer(id=1, name='John', type='engineer', engineer_name='Mr. Mech')
    assert isinstance(engineer, BaseModel)
    assert isinstance(engineer, pd_JTI_Employee)
    assert isinstance(engineer, pd_JTI_Engineer)


def test_inheritance_STI_Employee():
    """ Test Single Table Inheritance models """
    pd_STI_Employee = sa2.pydantic.sa_model(STI_Employee)
    assert set(schema_attrs(pd_STI_Employee)) == {
        'id', 'name', 'type',
    }

    pd_STI_Manager = sa2.pydantic.sa_model(STI_Manager, Parent=pd_STI_Employee)
    assert issubclass(pd_STI_Manager, pd_STI_Employee)  # correct inheritance
    assert set(schema_attrs(pd_STI_Manager)) == {
        # inherited
        'id', 'name', 'type',
        # self
        'manager_data', 'company_id',
    }

    pd_STI_Engineer = sa2.pydantic.sa_model(STI_Engineer, Parent=pd_STI_Employee)
    assert issubclass(pd_STI_Engineer, pd_STI_Employee)  # correct inheritance
    assert set(schema_attrs(pd_STI_Engineer)) == {
        # inherited
        'id', 'name', 'type',
        # self
        'engineer_info',
    }



def test_experiment_with_forward_references():
    """ ForwardRef experiments """

    # This is a playground.
    # First, see how pydantic classes play with forward references

    from typing import List, Optional, ForwardRef


    class pd_User(BaseModel):
        id: int = ...
        articles: List[ForwardRef('pd_Article')] = ...


    class pd_Article(BaseModel):
        id: int = ...
        user: Optional[ForwardRef('pd_User')] = ...

    def play_with_it():
        # evaluate forward references
        pd_User.update_forward_refs(pd_User=pd_User, pd_Article=pd_Article)
        # don't have to give all those variables to it
        pd_Article.update_forward_refs(**locals())

        pd_User(id=1, articles=[pd_Article(id=1, user=None)])
        pd_User(id=1, articles=[pd_Article(id=1, user=None)])
        pd_Article(id=1, user=None)
        pd_Article(id=1, user=pd_User(id=1, articles=[]))

    play_with_it()




    # Now do the same thing, but with dynamic class creation
    pd_User = type('pd_User', (BaseModel,), dict(
        id=...,
        articles=...,
        __module__=__name__,
        __annotations__=dict(
            id=int,
            articles=List[ForwardRef('pd_Article')],
        )
    ))

    pd_Article = type('pd_Article', (BaseModel,), dict(
        id=...,
        user=...,
        __module__=__name__,
        __annotations__=dict(
            id=int,
            user=Optional[ForwardRef('pd_User')],
        )
    ))

    play_with_it()


    # Now do the same thing, but with create_model()

    from pydantic import create_model

    pd_User = create_model(
        'pd_User',
        __module__=__name__,
        id=(int, ...),
        articles=(
            List[ForwardRef('pd_Article')],
            ...
        ),
    )

    pd_Article = create_model(
        'pd_Article',
        __module__=__name__,
        id=(int, ...),
        user=(
            Optional[ForwardRef('pd_User')],
            ...
        )
    )

    play_with_it()


@pytest.mark.skip('Not yet supported')
def test_sa_model_User_relationships():
    """ User: RELATIONSHIP, DYNAMIC_LOADER, ASSOCIATION_PROXY """
    # the difficult thing is that in a relationship, create_model()
    # has to refer to other models that have not been created yet.

    # Test User: relationships
    pd_User = sa2.pydantic.sa_model(User, types=AttributeType.RELATIONSHIP)

    # Test Article: relationships
    pd_Article = sa2.pydantic.sa_model(Article, types=AttributeType.RELATIONSHIP)

    # Test User: dynamic loader
    pd_User = sa2.pydantic.sa_model(User, types=AttributeType.DYNAMIC_LOADER)

    # Test User: association proxy
    pd_User = sa2.pydantic.sa_model(User, types=AttributeType.ASSOCIATION_PROXY)


@pytest.mark.skip('Not yet supported')
def test_sa_model_User_composite():
    """ User: COMPOSITE """
    # Difficulty: a composite refers to a type class which itself requires a pydantic model to work

    # Test User: composite
    pd_User = sa2.pydantic.sa_model(User, types=AttributeType.COMPOSITE)


# Extract __fields__ from schema
def schema_attrs(schema: Type[BaseModel]) -> Dict[str, dict]:
    return {
        field.alias: dict(type=field.type_, required=field.required, default=field.default)
        for field in schema.__fields__.values()
    }
