from typing import Any

from pydantic import BaseModel, ValidationError

from sa2schema import AttributeType, sa2

from .models import User, EnumType


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


# Extract __fields__ from schema
def schema_attrs(schema: BaseModel):
    return {
        field.alias: dict(type=field.type_, required=field.required, default=field.default)
        for field in schema.__fields__.values()
    }
