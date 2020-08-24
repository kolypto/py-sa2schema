from __future__ import annotations

import pytest
from typing import Any, Dict, Type, Callable, List, Optional, ForwardRef, Set
from pydantic import BaseModel, ValidationError, VERSION as PYDANTIC_VERSION
from pydantic.fields import SHAPE_LIST, ModelField
from pydantic.utils import GetterDict
from sqlalchemy.orm import exc as sa_exc, Session, load_only, joinedload
from sqlalchemy.orm.attributes import set_committed_value
from sqlalchemy.orm.base import instance_state
from sqlalchemy.orm.state import InstanceState

import sa2schema as sa2
from sa2schema import AttributeType
from sa2schema.to.pydantic import SALoadedModel, SAGetterDict, SALoadedGetterDict

from .models import Base, User, Article, Number, EnumType
from .models import JTI_Employee, JTI_Engineer
from .models import STI_Employee, STI_Manager, STI_Engineer


# region Test sa_model()


def test_sa_model_User_columns():
    """ User: COLUMN """
    # Test User: only columns
    pd_User = sa2.pydantic.sa_model(User, types=AttributeType.COLUMN,
                                    exclude=('int', 'json_attr'))
    assert schema_attrs(pd_User) == {
       'annotated_int': {'type': int, 'default': None, 'required': True},  # override from annotation!
        # note: `type` is always unwrappe by Pydantic. There never is `Optional[]` around it
       'default': {'type': str, 'default': 'value', 'required': False},  # default value is here
       'documented': {'type': str, 'default': None, 'required': False},
       'enum': {'type': EnumType, 'default': None, 'required': False},
       # 'int': {'type': int, 'default': None, 'required': False},  # excluded
       # 'json_attr': {'type': dict, 'default': None, 'required': False},  # excluded
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

        # Check
        assert schema_attrs(pd_User) == {
            'id': {'type': int, 'required': True, 'default': None},
            # It's normal that 'type' is without `List`.
            # The type is stored in ModelField.shape, and can also be seen in ModelField.outer_type_
            'articles': {'type': pd_Article, 'required': True, 'default': None}
        }
        assert pd_User.__fields__['articles'].shape == SHAPE_LIST

        assert schema_attrs(pd_Article) == {
            'id': {'type': int, 'required': True, 'default': None},
            'user': {'type': pd_User, 'required': True, 'default': None}
        }

        # Play
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


def test_sa_model_User_relationships():
    """ User: RELATIONSHIP, DYNAMIC_LOADER, ASSOCIATION_PROXY """
    # the difficult thing is that in a relationship, create_model()
    # has to refer to other models that have not been created yet.

    ns = sa2.pydantic.Models(__name__, 'pd_{model}', types=AttributeType.RELATIONSHIP)

    # Test User: relationships
    pd_User = ns.sa_model(User)
    pd_Article = ns.sa_model(Article)

    ns.update_forward_refs()  # got to do it

    if PYDANTIC_VERSION == '1.5':
        # 1.5: defaults with containers have Undefined
        from pydantic.fields import Undefined
        assert schema_attrs(pd_User) == {
            # All references resolved
            'articles_list': {'type': pd_Article, 'required': False, 'default': Undefined},
            'articles_set': {'type': pd_Article, 'required': False, 'default': Undefined},
            'articles_dict_attr': {'type': pd_Article, 'required': False, 'default': Undefined},
            'articles_dict_keyfun': {'type': pd_Article, 'required': False, 'default': Undefined}
        }
    elif PYDANTIC_VERSION == '1.5.1':
        # 1.5.1: 'default' is set to the container type
        assert schema_attrs(pd_User) == {
            # All references resolved
            'articles_list': {'type': pd_Article, 'required': False, 'default': []},
            'articles_set': {'type': pd_Article, 'required': False, 'default': set()},
            'articles_dict_attr': {'type': pd_Article, 'required': False, 'default': {}},
            'articles_dict_keyfun': {'type': pd_Article, 'required': False, 'default': {}}
        }
    elif PYDANTIC_VERSION == '1.6':
        # 1.6: BUG: nested models aren't resolved
        assert schema_attrs(pd_User) == {
            # All references resolved
            'articles_list': {'type': List[ForwardRef('pd_Article')], 'required': False, 'default': None},
            'articles_set': {'type': Set[ForwardRef('pd_Article')], 'required': False, 'default': None},
            'articles_dict_attr': {'type': Dict[Any, ForwardRef('pd_Article')], 'required': False, 'default': None},
            'articles_dict_keyfun': {'type': Dict[Any, ForwardRef('pd_Article')], 'required': False, 'default': None}
        }
    else:  # newer Pydantic
        # Newer Pydantics have pure `type` and no wrapper
        assert schema_attrs(pd_User) == {
            # All references resolved
            'articles_list': {'type': pd_Article, 'required': False, 'default': None},
            'articles_set': {'type': pd_Article, 'required': False, 'default': None},
            'articles_dict_attr': {'type': pd_Article, 'required': False, 'default': None},
            'articles_dict_keyfun': {'type': pd_Article, 'required': False, 'default': None}
        }

    assert schema_attrs(pd_Article) == {
        # All references resolved
        'user': {'type': pd_User, 'required': False, 'default': None},
    }

    # Play with it

    user = pd_User(articles_list=[],
                   articles_set=set(),
                   articles_dict_attr={},
                   articles_dict_keyfun={},
                   )

    user = pd_User(articles_list=[pd_Article()],
                   articles_set=set(),
                   articles_dict_attr={},
                   articles_dict_keyfun={},
                   )

    user = pd_User(articles_list=[],
                   articles_set=set(),
                   articles_dict_attr={'a': pd_Article()},
                   articles_dict_keyfun={},
                   )

    article = pd_Article()

    article = pd_Article(user=user)

    # Test User: dynamic loader
    pd_User = sa2.pydantic.sa_model(User, types=AttributeType.DYNAMIC_LOADER, naming='pd_{model}', module=__name__)
    pd_User.update_forward_refs(**locals())  # manually

    if PYDANTIC_VERSION == '1.5':
        # 1.5: defaults with containers have Undefined
        from pydantic.fields import Undefined
        assert schema_attrs(pd_User) == {
            # All references resolved
            'articles_q': {'type': pd_Article, 'required': False, 'default': Undefined},
        }
    elif PYDANTIC_VERSION == '1.5.1':
        # 1.5.1: 'default' is set to the container type
        assert schema_attrs(pd_User) == {
            # All references resolved
            'articles_q': {'type': pd_Article, 'required': False, 'default': []},
        }
    elif PYDANTIC_VERSION == '1.6':
        # 1.6: BUG: nested models aren't resolved
        assert schema_attrs(pd_User) == {
            'articles_q': {'type': List[ForwardRef('pd_Article')], 'required': False, 'default': None},
        }
    else:
        # Newer Pydantics has pure types
        assert schema_attrs(pd_User) == {
            # All references resolved
            'articles_q': {'type': pd_Article, 'required': False, 'default': None},
        }

    # Test User: association proxy
    pd_User = sa2.pydantic.sa_model(User, types=AttributeType.ASSOCIATION_PROXY, naming='pd_{model}', module=__name__)
    pd_User.update_forward_refs(**locals())  # manually

    if PYDANTIC_VERSION == '1.5':
        # 1.5: defaults with containers have Undefined
        from pydantic.fields import Undefined
        assert schema_attrs(pd_User) == {
            # All references resolved
            'article_titles': {'type': pd_Article, 'required': False, 'default': Undefined},
        }
    elif PYDANTIC_VERSION == '1.5.1':
        # 1.5.1: 'default' is set to the container type
        assert schema_attrs(pd_User) == {
            # All references resolved
            'article_titles': {'type': pd_Article, 'required': False, 'default': {}},
        }
    elif PYDANTIC_VERSION == '1.6':
        # 1.6: BUG: nested models aren't resolved
        assert schema_attrs(pd_User) == {
            # All references resolved
            'article_titles': {'type': Dict[str, ForwardRef('pd_Article')], 'required': False, 'default': None},
        }
    else:
        # Newer Pydantics has pure types
        assert schema_attrs(pd_User) == {
            # All references resolved
            'article_titles': {'type': pd_Article, 'required': False, 'default': None},
        }


def test_sa_model_user_relationships_in_annotations():
    """ Test annotated classes """

    # Declare some models
    import sqlalchemy as sa
    from sqlalchemy.ext.declarative import declarative_base

    Base = declarative_base()

    class User(Base):
        __tablename__ = 'users'
        id = sa.Column(sa.Integer, primary_key=True)

        # Annotated relationship
        articles: List[Article] = sa.orm.relationship(lambda: Article)

    class Article(Base):
        __tablename__ = 'articles'
        id = sa.Column(sa.Integer, primary_key=True)
        user_id = sa.Column(sa.ForeignKey(User.id))

        # Annotated relationship
        user: User = sa.orm.relationship(User)

    # sa_model() them
    # This `Article` annotation used to raise the error:
    #       RuntimeError: no validator found for <class 'tests.models.Article'>,
    #       see `arbitrary_types_allowed` in Config
    # which meant that the annotation wasn't converted into a proper ForwardRef.
    # So in this test, if the error isn't raised, everything went fine
    models = sa2.pydantic.Models(__name__, types=AttributeType.ALL, naming='{model}Model')
    models.sa_model(User)
    models.sa_model(Article)
    models.update_forward_refs()

    # Use it: no errors
    user = User(
        id=1,
        articles=[Article(id=1)]
    )
    pd_user = models.User.from_orm(user)
    assert pd_user.dict() == dict(
        id=1,
        articles=[
            dict(id=1, user_id=None, user=None)
        ]
    )


def test_sa_model_User_composite():
    """ User: COMPOSITE """
    # Difficulty: a composite refers to a type class which itself requires a pydantic model to work

    # Test User: composite
    pd_User = sa2.pydantic.sa_model(User, types=AttributeType.COMPOSITE, module=__name__)

    # resolution will fail: `Point` is not defined
    with pytest.raises(NameError):
        pd_User.update_forward_refs()

    # Define a model for this custom class
    # Notice that unlike relationships, we expect the model to have the very same name.
    # You can provide is as a keyword to update_forward_refs() if it doesn't
    class Point(BaseModel):
        pass

    # now it will work
    pd_User.update_forward_refs(Point=Point)

    # Check
    assert schema_attrs(pd_User) == {
        # All references resolved
        'point': {'type': Point, 'required': True, 'default': None},
        'synonym': {'type': Point, 'required': True, 'default': None},
    }


def test_sa_model_User_make_optional():
    """ User: make_optional() """

    # Partial User: make_optional=True
    pd_User = sa2.pydantic.sa_model(User, make_optional=True)

    everything_is_nullable = {
       # Everything is nullable and not required
        'annotated_int': {'allow_none': True, 'required': False},
       'default': {'allow_none': True, 'required': False},
       'documented': {'allow_none': True, 'required': False},
       'enum': {'allow_none': True, 'required': False},
       'int': {'allow_none': True, 'required': False},
       'json_attr': {'allow_none': True, 'required': False},
       'optional': {'allow_none': True, 'required': False},
       'required': {'allow_none': True, 'required': False},
    }

    assert schema_attrs_extract(pd_User, lambda field: dict(
        required=field.required,
        allow_none=field.allow_none,
    )) == everything_is_nullable

    # Partial User, make_optional=ALL_BUT_PRIMARY_KEY
    pd_User = sa2.pydantic.sa_model(User, make_optional=sa2.filter.ALL_BUT_PRIMARY_KEY)

    assert schema_attrs_extract(pd_User, lambda field: dict(
        required=field.required,
        allow_none=field.allow_none,
    )) == {
        **everything_is_nullable,
        # Primary key: required, not nullable
        # This is because ALL_BUT_PRIMARY_KEY is used
        'annotated_int': {'allow_none': False, 'required': True},
    }


# endregion


# region Test from_orm()


def test_sa_model_from_orm_instance():
    """ Test how GetterDict works with SqlAlchemy models, and how sa_model() works with it """
    # Internally, it uses some really generic stuff (dir()) which might not always play nicely with SqlAlchemy
    # in some complex cases like inheritance, default values, unloaded attributes, etc.


    # Test 3 models: full, partial, partial & only loaded
    pd_Number = sa2.pydantic.sa_model(Number)
    pd_NumberPartial = sa2.pydantic.sa_model(Number, make_optional=True)
    pdl_NumberPartial = sa2.pydantic.sa_model(Number, make_optional=True, Parent=SALoadedModel)



    # === Test: Number(), has no database identity, all defaults
    n = Number()  # nothing's set

    all_none = dict(id=None, n=None, nd1=None, nd2=None, nd3=None, d1=None, d2=None, d3=None)

    # Try GetterDicts
    assert dict(GetterDict(n)) == dict(
        # Everything's None
        **all_none,
        # WARNING: this is an alien and should not be here at all
        metadata=Number.metadata,
    )

    assert dict(SAGetterDict(n)) == dict(
        **all_none,
        # metadata  # the alien is not reported
    )

    assert dict(SALoadedGetterDict(n)) == all_none

    # Try to extract

    # pd_Number: will fail because it has required fields
    with pytest.raises(ValidationError):
        pd_Number.from_orm(n)  # ValidationError: can't return a partial model

    # pd_NumberPartial: will succeed
    pdn: pd_NumberPartial = pd_NumberPartial.from_orm(n)
    assert pdn.dict() == dict(
        **all_none,  # Everything's None
        # metadata  # the alien is not reported
    )

    pdl: pdl_NumberPartial = pdl_NumberPartial.from_orm(n)
    assert pdl.dict() == all_none

    # Use dict(exclude_unset=True)
    assert pdn.dict(exclude_unset=True) == dict(**all_none)
    assert pdl.dict(exclude_unset=True) == dict()  # notice how SALoadedModel removed unloaded attributes



    # === Test: Number(), has no database identity, all values set
    # Note: the primary key is not yet set :)
    init_fields = dict(n=None, nd1=None, nd2=None, nd3=None, d1=0, d2=0, d3=0)
    n = Number(**init_fields)

    # Try GetterDicts
    assert dict(GetterDict(n)) == dict(
        id=None,  # the default is here
        **init_fields,  # same
        metadata=Number.metadata  # Alien
    )

    assert dict(SAGetterDict(n)) == dict(
        id=None,
        **init_fields,
        #metadata  # the alien is not reported
    )

    assert dict(SALoadedGetterDict(n)) == dict(id=None, **init_fields)

    # Try to extract

    # pd_Number: will fail because it has required fields
    with pytest.raises(ValidationError):
        pd_Number.from_orm(n)  # ValidationError: can't return a partial model

    # pd_NumberPartial: will succeed
    pdn: pd_NumberPartial = pd_NumberPartial.from_orm(n)  # doesn't fail
    assert pdn.dict() == dict(
        **init_fields,  # exactly!
        id=None,  # primary key
    )

    pdl: pdl_NumberPartial = pdl_NumberPartial.from_orm(n)
    assert pdl.dict() == dict(id=None, **init_fields)



    # === Test: Number(), persistent, all fields loaded
    committed_values = dict(id=1, n=None, nd1=None, nd2=None, nd3=None, d1=0, d2=0, d3=0)

    n = Number()
    for k, v in committed_values.items():
        set_committed_value(n, k, v)

    # extract

    pd = pd_Number.from_orm(n)
    assert pd.dict() == committed_values

    pdn: pd_NumberPartial = pd_NumberPartial.from_orm(n)
    assert pdn.dict() == committed_values

    pdl: pdl_NumberPartial = pdl_NumberPartial.from_orm(n)
    assert pdl.dict() == committed_values



    # === Test: Number(), persistent, all fields loaded, but modified
    modified_values = dict(id=2, n=3, nd1=4, nd2=5, nd3=6)
    final_modified_values = {**committed_values, **modified_values}

    for k, v in modified_values.items():
        setattr(n, k, v)

    # extract

    pd = pd_Number.from_orm(n)
    assert pd.dict() == final_modified_values

    pdn: pd_NumberPartial = pd_NumberPartial.from_orm(n)
    assert pdn.dict() == final_modified_values

    pdl: pdl_NumberPartial = pdl_NumberPartial.from_orm(n)
    assert pdl.dict() == final_modified_values



    # === Test: Number(), persistent, unloaded and expired fields
    n = sa_set_committed_state(Number(), id=1, n=2, nd1=3, nd2=4, nd3=5, d1=6, d2=7, d3=8)

    # expire attributes (the way SqlAlchemy does it internally)
    # This makes them unloaded, and SALoadedGetterDict will ignore them
    expire_sa_instance(n,
        'n', 'nd1', 'nd2',  # expire some nullable attributes
        'd1', 'd2',  # expire some non-nullable attributes
    )

    # extract

    with pytest.raises(sa_exc.DetachedInstanceError):
        # Will fail because it will try to load an attribute, but there's no Session available ;)
        # This is expected to fail because it uses the default Pydantic GetterDict
        pd = pd_Number.from_orm(n)

    with pytest.raises(sa_exc.DetachedInstanceError):
        # Also attempts loading; can't do that in this test
        pdn: pd_NumberPartial = pd_NumberPartial.from_orm(n)

    pdl: pdl_NumberPartial = pdl_NumberPartial.from_orm(n)  # doesn't fail
    assert pdl.dict() == dict(
        id=1, nd3=5, d3=8,  # loaded
        # all expired attributes are None
        n=None, nd1=None, nd2=None,
        d1=None, d2=None,
    )


def test_User_from_orm_instance():
    """ Make a sa_model() from a complex entity and from_orm() it """
    # Models
    pd_User = sa2.pydantic.sa_model(User)
    pdl_UserPartial = sa2.pydantic.sa_model(User, make_optional=True, Parent=SALoadedModel)

    # Instances
    with pytest.raises(ValidationError):
        # Fails: required fields not provided
        pd_User.from_orm(User())

    with pytest.raises(ValidationError):
        # Fails: required fields not provided
        pd_User.from_orm(User(annotated_int='1'))

    with pytest.raises(ValidationError):
        # Fails: required fields not provided
        pd_User.from_orm(User(annotated_int='1', required=2))

    # This is the minimal user that works
    user = User(annotated_int='1', required=2, default='3')

    # extract
    pd_user = pd_User.from_orm(user)
    assert pd_user.dict() == dict(
        # The values we've provided
        annotated_int=1,
        required='2',
        default='3',
        # Everyone else is `None`
        int=None,
        enum=None,
        optional=None,
        documented=None,
        json_attr=None,
    )

    # Expire it
    expire_sa_instance(user, *pd_user.dict())  # expire all keys

    # extract
    with pytest.raises(sa_exc.DetachedInstanceError):
        # attempts loading
        pd_User.from_orm(user)

    pdl_user = pdl_UserPartial.from_orm(user)  # no error: ignores unloaded
    assert pdl_user.dict() == dict(
        # Everything's a None
        annotated_int=None,
        required=None,
        default=None,
        int=None,
        enum=None,
        optional=None,
        documented=None,
        json_attr=None,
    )


def test_plain_recursion():
    """ Test how Pydantic works with recursion """
    # Two classes that link to one another
    # call them xUser and xArticle so they don't conflict with `User` and `Article` from the outer scope

    class xUser(BaseModel):
        id: int
        articles: List[xArticle]

    class xArticle(BaseModel):
        id: int
        author: Optional[xUser] = None

    xUser.update_forward_refs(xArticle=xArticle)
    xArticle.update_forward_refs(xUser=xUser)

    # === Test 1. Recursive models parsed
    article_dict = dict(id=1)
    user_dict = dict(id=1, articles=[article_dict])
    article_dict['author'] = user_dict

    with pytest.raises(RecursionError):
        # It also falls into infinite recursion
        user = xUser(**user_dict)

    # === Test 2. Recursive models linked
    # Link two models
    article = xArticle(id=1)
    user = xUser(id=1, articles=[article])

    assert user.dict() == dict(  # no problem yet
        id=1,
        articles=[{'author': None, 'id': 1}]
    )

    # Make a circular dependency
    # No error here
    article.author = user
    user.articles = [article]

    with pytest.raises(RecursionError):
        # Okay, at the moment, Pydantic is not able to detect cyclic dependencies and just fails on those.
        # This means that our models cannot have those.
        # The problem is that SqlAlchemy routinely makes cyclic references; e.g. with relationships.
        # Until this is solved, there is no solution to the problem.
        # You just have to exclude those fields from your models.
        user.dict()


def test_User_from_orm_instance_with_relationships():
    """ Use sa_model().from_orm() with relationships """
    user_exclude = lambda name: name not in ('articles_list',)

    # === Test: Models
    # make the namespace
    pd_models = sa2.pydantic.Models(__name__, types=AttributeType.RELATIONSHIP,
                                    naming='pd_{model}')
    pd_User = pd_models.sa_model(User, exclude=user_exclude)
    pd_Article = pd_models.sa_model(Article,
                                    types=AttributeType.COLUMN,  # also include columns
                                    )
    pd_models.update_forward_refs()

    # check that __getattr__() works as advertised
    assert pd_User is pd_models.User
    assert pd_Article is pd_models.Article

    # Empty user
    user = User()

    pd_user = pd_User.from_orm(user)
    assert pd_user.dict() == dict(
        # Looks like they come straight from SqlAlchemy
        articles_list=[]
    )

    # Article
    article = Article(id=1, title='a')

    pd_article = pd_Article.from_orm(article)
    assert pd_article.dict() == dict(id=1, title='a', user=None, user_id=None)

    # User with articles
    user = User(articles_list=[article])  # NOTE: SqlAlchemy has already provided a bi-directional link

    pd_user = pd_User.from_orm(user)
    assert pd_user.dict() == dict(
        articles_list=[
            dict(
                id=1,
                title='a',
                user=None,  # NOTE: replaced with `None` to avoid RecursionError ;)
                user_id=None
            ),
        ],
    )

    # === Test: Partial models
    pd_models_partial = sa2.pydantic.Models(__name__, types=AttributeType.RELATIONSHIP,
                                            naming='pd_{model}Partial', make_optional=True)
    pd_UserPartial = pd_models_partial.sa_model(User, exclude=user_exclude)
    pd_ArticlePartial = pd_models_partial.sa_model(Article)
    pd_models_partial.update_forward_refs()

    # User with articles
    article = Article(id=1, title='a')
    user = User(articles_list=[article])

    pd_user = pd_UserPartial.from_orm(user)
    assert pd_user.dict() == dict(
        articles_list=[
            dict(
                user=None,  # NOTE: replaced with `None` to avoid RecursionError ;)
            )
        ],
    )


    # === Test: Partial models, only loaded
    pdl_models_partial = sa2.pydantic.Models(__name__, types=AttributeType.RELATIONSHIP,
                                             naming='pdl_{model}Partial', make_optional=True,
                                             Base=SALoadedModel)
    pdl_UserPartial = pdl_models_partial.sa_model(User, exclude=user_exclude)
    pdl_ArticlePartial = pdl_models_partial.sa_model(Article)
    pdl_models_partial.update_forward_refs()

    # Make a User with unloaded relationships
    article = Article(id=1, title='a')
    user = sa_set_committed_state(User(), articles_list=[article])
    expire_sa_instance(user, 'articles_list')

    # Loaded model: will work fine
    pdl_user = pdl_UserPartial.from_orm(user)
    assert pdl_user.dict() == dict(
        articles_list=None,  # not loaded (expired)
    )


def test_from_orm_with_properties():
    """ Test from_orm() with @properties """
    # Prepare a model that takes @property into consideration
    pd_User = sa2.pydantic.sa_model(
        User, SALoadedModel,
        types=AttributeType.COLUMN | AttributeType.PROPERTY_R,
        make_optional=True,  # all fields are optional
    )

    # Now here is the issue that I had.
    # `SALoadedModel` is a smart model that only reports fields that are loaded. It won't trigger lazy loading.
    # But here's a catch. @property.
    # When you load a property, you have literally no idea what other attributes it may trigger.
    # This may result in numerous lazy-loads.
    # That's unacceptable.

    # For this reason, we annotate properties with the list of attributes it depends upon.
    # A property would only be included if those attributes have been loaded.
    # Un-annotated properties won't be loaded at all, because the consequences are potentially destructive.

    # User.documented is not set
    # This means that User.property_documented that relies on it won't be retrieved
    # No other properties are even considered
    user = sa_set_committed_state(User(), int=1)
    assert pd_User.from_orm(user).dict(exclude_unset=True) == {
        # The only loaded attribute
        'int': 1,
    }

    # User.documented is set
    # User.property_documented can now be retrieved
    user = sa_set_committed_state(User(), int=1, documented='hey')
    assert pd_User.from_orm(user).dict(exclude_unset=True) == {
        'int': 1,
        'documented': 'hey',
        # @property is now retrieved because `documented` is loaded
        'property_documented': 'hey',
    }

# endregion


def test_with_real_sqlalchemy_session(sqlite_session: Session):
    ssn = sqlite_session

    # One user, one article
    article = Article(id=1, title='1')
    user = User(annotated_int=1, default='', required='',
                articles_list=[article])

    # Populate the DB
    ssn.begin()
    ssn.add(user)
    ssn.add(article)
    ssn.commit()

    # Prepare Pydantic models
    # We'll be using partial, only-loaded, models
    # We're interested in relationships (User) and columns (Article)
    g = sa2.pydantic.Models(__name__,
                            types=AttributeType.RELATIONSHIP,
                            naming='pd_{model}Partial',
                            make_optional=True, Base=SALoadedModel)

    pd_UserPartial = g.sa_model(User)
    pd_ArticlePartial = g.sa_model(Article,
                                   types=AttributeType.COLUMN,
                                   )
    g.update_forward_refs()


    # === Test: Columns: dummy Article (not in DB)
    article = Article()  # no attributes set
    pd_article = pd_ArticlePartial.from_orm(article)
    assert pd_article.dict() == dict(
        id=None,
        title=None,
        user_id=None,  # all None
        user=None,  # not set
    )

    article = Article(id=1, title='1')  # some attributes set
    pd_article = pd_ArticlePartial.from_orm(article)
    assert pd_article.dict() == dict(
        id=1, title='1',
        user_id=None,  # gets a `None`
        user=None,  # not set
    )

    # === Test: Columns: load a full Article
    article = ssn.query(Article).first()

    pd_article = pd_ArticlePartial.from_orm(article)
    assert pd_article.dict() == dict(
        id=1,
        title='1',
        user_id='1',
        user=None,  # not loaded
    )

    assert pd_article.dict(exclude_unset=True) == dict(
        id=1,
        title='1',
        user_id='1',
        # unloaded attributes are not listed because of `exclude_unset`
    )

    # === Test: Columns: load a full Article + Article.user
    article = ssn.query(Article).options(joinedload(Article.user)).first()

    pd_article = pd_ArticlePartial.from_orm(article)
    assert pd_article.dict() == dict(
        id=1,
        title='1',
        user_id='1',
        user=dict(
            articles_list=None,  # not loaded
            articles_set=None,  # not loaded
            articles_dict_attr=None,  # not loaded
            articles_dict_keyfun=None,  # not loaded
        ),
    )

    assert pd_article.dict(exclude_unset=True) == dict(
        id=1,
        title='1',
        user_id='1',
        user=dict(
            # unloaded attributes are not listed because of `exclude_unset`
        )
    )

    # === Test: Columns: load a full Article + Article.user + Article.user.articles_list
    article = ssn.query(Article).options(joinedload(Article.user).joinedload(User.articles_list)).first()

    pd_article = pd_ArticlePartial.from_orm(article)
    assert pd_article.dict() == dict(
        id=1,
        title='1',
        user_id='1',
        user=dict(
            articles_list=[None],  # loaded, but replaced with `None` due to recursion (!)
            articles_set=None,  # not loaded
            articles_dict_attr=None,  # not loaded
            articles_dict_keyfun=None,  # not loaded
        ),
    )

    # === Test: Columns: load a deferred Article
    ssn.expunge_all()
    article = ssn.query(Article).options(load_only('id')).first()

    pd_article = pd_ArticlePartial.from_orm(article)
    assert pd_article.dict() == dict(
        id=1,
        title=None,  # not loaded
        user_id=None,  # not loaded
        user=None,  # not loaded
    )

    # === Test: Columns: expired Article
    article = ssn.query(Article).first()
    ssn.expire(article)

    pd_article = pd_ArticlePartial.from_orm(article)
    assert pd_article.dict() == dict(
        id=None, title=None, user_id=None, user=None,  # all expired
    )

    # === Test: Relationships: dummy User
    user = User()  # empty
    pd_user = pd_UserPartial.from_orm(user)
    assert pd_user.dict() == dict(
        articles_list=None,  # not loaded
        articles_set=None,
        articles_dict_attr=None,
        articles_dict_keyfun=None,
    )

    user = User(articles_list=[Article(title='')])  # with some articles
    pd_user = pd_UserPartial.from_orm(user)
    assert pd_user.dict() == dict(
        articles_list=[{'id': None, 'title': '', 'user_id': None,
                        'user': None,  # NOTE: replaced with `None` to avoid RecursionError ;)
                        }],
        articles_set=None,
        articles_dict_attr=None,
        articles_dict_keyfun=None,
    )

    # === Test: Relationships: load a deferred User
    user = ssn.query(User).first()
    assert pd_UserPartial.from_orm(user).dict() == dict(
        articles_list=None,  # not loaded
        articles_set=None,
        articles_dict_attr=None,
        articles_dict_keyfun=None,
    )

    # === Test: Relationships: load a full User
    user = ssn.query(User).options(joinedload(User.articles_list)).first()
    assert pd_UserPartial.from_orm(user).dict() == dict(
        articles_list=[
            # Now included because loaded! Yay!
            {'id': 1, 'title': '1', 'user_id': '1',
             'user': None,  # NOTE: replaced with `None` to avoid RecursionError ;)
             }
        ],
        articles_set=None,
        articles_dict_attr=None,
        articles_dict_keyfun=None,
    )

    # === Test: Relationships: expired User
    user = ssn.query(User).options(joinedload(User.articles_list)).first()
    ssn.expire(user)

    assert pd_UserPartial.from_orm(user).dict() == dict(
        articles_list=None,  # expired now
        articles_set=None,
        articles_dict_attr=None,
        articles_dict_keyfun=None,
    )

    # === Test: Columns: deleted
    article = ssn.query(Article).first()
    ssn.begin()
    ssn.delete(article)
    ssn.flush()

    pd_article = pd_ArticlePartial.from_orm(article)
    assert pd_article.dict() == dict(
        id=1, title='1', user_id='1',  # still available
        user={  # loaded by cascade loader when deleting
            'articles_list': None,
            'articles_set': None,
            'articles_dict_attr': None,
            'articles_dict_keyfun': None,
        }
    )

    ssn.rollback()  # bring the article back
    article = ssn.query(Article).first()
    assert article  # still around

    # === Test: Relationships: deleted
    user = ssn.query(User).options(joinedload(User.articles_list)).first()
    ssn.begin()
    ssn.delete(user)
    ssn.flush()

    pd_user = pd_UserPartial.from_orm(user)
    assert pd_user.dict() == dict(
        # Unbelievable. All relationships are loaded on delete() :)
        # This is because SqlAlchemy was getting ready for active CASCADE
        articles_list=[
            {'id': 1, 'title': '1', 'user_id': None,
             'user': None,  # NOTE: replaced with `None` to avoid RecursionError ;)
             },
        ],
        articles_set=None,  # not loaded for some reason
        articles_dict_attr={
            1: {'id': 1, 'title': '1', 'user_id': None, 'user': None},
        },
        articles_dict_keyfun={
            1001: {'id': 1, 'title': '1', 'user_id': None, 'user': None},
        },
    )


def test_derive_model():
    # Create a model
    class Animal(BaseModel):
        id: int
        name: str
        age: int

    assert set(Animal.__fields__) == {'id', 'name', 'age'}

    # Derive a model

    SecretAnimal = sa2.pydantic.derive_model(Animal, 'SecretAnimal', exclude=('name', 'age'))
    assert set(SecretAnimal.__fields__) == {'id'}  # only one field left


# TODO: test field name conflicts with pydantic (aliasing)


# Extract __fields__ from schema
def schema_attrs(schema: Type[BaseModel]) -> Dict[str, dict]:
    """ Extract field info from a Pydantic schema """
    return schema_attrs_extract(schema, lambda field: dict(
        type=field.type_,
        required=field.required,
        # allow_none=field.allow_none,
        default=field.default,
    ))


def schema_attrs_extract(schema: Type[BaseModel], extractor: Callable[[ModelField], dict]) -> Dict[str, dict]:
    """ Walk a Pydantic model and extract info from every field with a callback """
    field: ModelField
    return {
        field.alias: extractor(field)
        for field in schema.__fields__.values()
    }


def sa_set_committed_state(obj: object, **committed_values):
    """ Put values into an SqlAlchemy instance as if they were committed to the DB """
    # Give it some DB identity so that SA thinks it can load something
    state: InstanceState = instance_state(obj)
    state.key = object()

    # Set every attribute in such a way that SA thinkg that's the way it looks in the DB
    for k, v in committed_values.items():
        set_committed_value(obj, k, v)

    return obj


def expire_sa_instance(obj: object, *attribute_names):
    """ Mark SqlAlchemy's instance fields as 'expired' """
    state: InstanceState = instance_state(obj)
    state._expire_attributes(state.dict, attribute_names)
