from typing import List, Set, Dict, Any

from sa2schema import sa_model_primary_key_names, sa_model_primary_key_info
from sa2schema import sa_model_attributes_by_type
from sa2schema import all_sqlalchemy_model_attribute_names
from sa2schema import sa_model_info, sa_attribute_info, AttributeType
from sa2schema.info.attribute import (
    NOT_PROVIDED,
    ColumnInfo,
    PropertyInfo, HybridPropertyInfo, HybridMethodInfo,
    CompositeInfo, ColumnExpressionInfo,
    RelationshipInfo, AssociationProxyInfo, DynamicLoaderInfo
)
from .models import *


def test_all_sqlalchemy_model_attribute_names():
    """ Test all_sqlalchemy_model_attribute_names() """
    assert sa_model_primary_key_names(User) == ('annotated_int',)
    assert all_sqlalchemy_model_attribute_names(User) == (
        # Everything in the order it was defined on the class
        '_ignored',
        'annotated_int',
        'int',
        'enum',
        'optional',
        'required',
        'default',
        'documented',
        'json_attr',
        'property_without_type',
        'property_typed',
        'property_documented',
        'property_nullable',
        'property_writable',
        'hybrid_property_typed',
        'hybrid_property_writable',
        'hybrid_method_attr',
        'expression',
        'point',
        'synonym',
        'articles_list',
        'articles_set',
        'articles_dict_attr',
        'articles_dict_keyfun',
        'article_titles',
        'article_authors',
        'articles_q',
    )

    assert sa_model_primary_key_names(Article) == ('id',)
    assert all_sqlalchemy_model_attribute_names(Article) == (
        'id',
        'user_id',
        'title',
        'user',
    )

    assert sa_model_primary_key_names(Number) == ('id',)
    assert all_sqlalchemy_model_attribute_names(Number) == (
        'id',
        'n',
        'nd1',
        'nd2',
        'nd3',
        'd1',
        'd2',
        'd3',
    )
    # Check inherited properties

    Base = declarative_base()

    class A(Base):
        __tablename__ = 'a'
        id = sa.Column(sa.Integer, primary_key=True)
        type = sa.Column(sa.String)

        __mapper_args__ = {
            'polymorphic_identity': 'a',
            'polymorphic_on': type
        }

        @property
        def number(self):
            pass

    class B(A):
        __mapper_args__ = {
            'polymorphic_identity': 'b',
        }

    assert all_sqlalchemy_model_attribute_names(B) == (
        'id', 'type',
        # Inherited property
        'number',
    )


def test_sa_model_info_extraction__User():
    """ Test sa_model_info(User) """
    generated_fields = sa_model_info(User, types=AttributeType.ALL, exclude=())
    expected_fields = {
        '_ignored': ColumnInfo(  # not ignored in sa_model_info() ; ignored in sa_model()
            attribute_type=AttributeType.COLUMN,
            attribute=User._ignored,
            primary_key=False,
            foreign_key=False,
            nullable=True,
            readable=True,
            writable=True,
            value_type=str,
            default=None,
            default_factory=None,
            doc=None
        ),
        'annotated_int': ColumnInfo(
            attribute_type=AttributeType.COLUMN,
            attribute=User.annotated_int,
            primary_key=True,
            foreign_key=False,
            nullable=False,
            readable=True,
            writable=True,
            value_type=str,  # annotations are ignored here
            default=NOT_PROVIDED,
            default_factory=None,
            doc=None
        ),
        'int': ColumnInfo(
            attribute_type=AttributeType.COLUMN,
            attribute=User.int,
            primary_key=False,
            foreign_key=False,
            nullable=True,
            readable=True,
            writable=True,
            value_type=int,  # type is here
            default=None,  # nullable columns always have this default
            default_factory=None,
            doc=None
        ),
        'enum': ColumnInfo(
            attribute_type=AttributeType.COLUMN,
            attribute=User.enum,
            primary_key=False,
            foreign_key=False,
            nullable=True,
            readable=True,
            writable=True,
            value_type=EnumType,  # type is here
            default=None,  # nullable column
            default_factory=None,
            doc=None
        ),
        'optional': ColumnInfo(
            attribute_type=AttributeType.COLUMN,
            attribute=User.optional,
            primary_key=False,
            foreign_key=False,
            nullable=True,  # optional
            readable=True,
            writable=True,
            value_type=str,  # type is not wrapped in Optional[]
            default=None,  # nullable column
            default_factory=None,
            doc=None
        ),
        'required': ColumnInfo(
            attribute_type=AttributeType.COLUMN,
            attribute=User.required,
            primary_key=False,
            foreign_key=False,
            nullable=False,  # required
            readable=True,
            writable=True,
            value_type=str,
            default=NOT_PROVIDED,  # non-nullable columns get this
            default_factory=None,
            doc=None
        ),
        'default': ColumnInfo(
            attribute_type=AttributeType.COLUMN,
            attribute=User.default,
            primary_key=False,
            foreign_key=False,
            nullable=False,  # not nullable
            readable=True,
            writable=True,
            value_type=str,
            default='value',  # default value
            default_factory=None,
            doc=None
        ),
        'documented': ColumnInfo(
            attribute_type=AttributeType.COLUMN,
            attribute=User.documented,
            primary_key=False,
            foreign_key=False,
            nullable=True,
            readable=True,
            writable=True,
            value_type=str,
            default=None,  # nullable column
            default_factory=None,
            doc='Some descriptive text'  # doc=text
        ),
        'json_attr': ColumnInfo(
            attribute_type=AttributeType.COLUMN,
            attribute=User.json_attr,
            primary_key=False,
            foreign_key=False,
            nullable=True,
            readable=True,
            writable=True,
            # JSON defaults to dict in SqlAlchemy
            value_type=dict,
            default=None,  # nullable column
            default_factory=None,
            doc=None
        ),
        'property_without_type': PropertyInfo(
            attribute_type=AttributeType.PROPERTY_R,  # no setter
            attribute=User.property_without_type,
            nullable=True,  # no type. No idea. May be null as well.
            readable=True,
            writable=False,  # no setter
            loads_attributes=None,
            value_type=Any,  # no idea
            default=NOT_PROVIDED,
            default_factory=None,
            doc=None
        ),
        'property_typed': PropertyInfo(
            attribute_type=AttributeType.PROPERTY_R,  # no setter
            attribute=User.property_typed,
            nullable=False,  # return value is not Optional[]
            readable=True,
            writable=False,  # no setter
            loads_attributes=None,
            value_type=str,
            default=NOT_PROVIDED,
            default_factory=None,
            doc=None
        ),
        'property_documented': PropertyInfo(
            attribute_type=AttributeType.PROPERTY_R,  # no setter
            attribute=User.property_documented,
            nullable=True,  # no return value. May be null.
            readable=True,
            writable=False,  # no setter
            loads_attributes={'documented'},  # read from @loads_attributes()
            value_type=Any,  # no return value
            default=NOT_PROVIDED,
            default_factory=None,
            doc=' Documented property '
        ),
        'property_nullable': PropertyInfo(
            attribute_type=AttributeType.PROPERTY_R,  # no setter
            attribute=User.property_nullable,
            nullable=True,  # explicitly Optional[]
            readable=True,
            writable=False,  # no setter
            loads_attributes=None,
            value_type=str,  # unwrapped
            default=NOT_PROVIDED,
            default_factory=None,
            doc=None,
        ),
        'property_writable': PropertyInfo(
            attribute_type=AttributeType.PROPERTY_RW,  # setter provided
            attribute=User.property_writable,
            nullable=False,  # no Optional[]
            readable=True,
            writable=True,  # with setter
            loads_attributes=None,
            value_type=str,  # type
            default='default',  # from setter's argument
            default_factory=None,
            doc=None,
        ),
        'hybrid_property_typed': HybridPropertyInfo(
            attribute_type=AttributeType.HYBRID_PROPERTY_R,  # no setter
            attribute=User.hybrid_property_typed.descriptor,
            nullable=False,  # no Optional[]
            readable=True,
            writable=False,  # no setter
            loads_attributes=None,
            value_type=str,  # type
            default=NOT_PROVIDED,
            default_factory=None,
            doc=None,
        ),
        'hybrid_property_writable': HybridPropertyInfo(
            attribute_type=AttributeType.HYBRID_PROPERTY_RW,  # setter
            attribute=User.hybrid_property_writable.descriptor,
            nullable=False,  # no Optional[]
            readable=True,
            writable=True,  # setter
            loads_attributes=None,
            value_type=str,  # type
            default='default',  # from setter's argument
            default_factory=None,
            doc=None,
        ),
        'hybrid_method_attr': HybridMethodInfo(
            attribute_type=AttributeType.HYBRID_METHOD,
            attribute=User.__mapper__.all_orm_descriptors.hybrid_method_attr,
            nullable=True,
            readable=True,
            writable=False,
            value_type=Any,  # no return annotation
            default=NOT_PROVIDED,
            default_factory=None,
            doc=None,
        ),
        'expression': ColumnExpressionInfo(
            attribute_type=AttributeType.EXPRESSION,
            attribute=User.expression,
            nullable=True,
            readable=True,
            writable=False,
            value_type=int,  # sqlalchemy knows!
            default=NOT_PROVIDED,
            default_factory=None,
            doc=None,
        ),
        'point': CompositeInfo(
            attribute_type=AttributeType.COMPOSITE,
            attribute=User.point,
            nullable=False,  # composites aren't nullable
            readable=True,
            writable=True,  # it's wriable
            value_type=Point,  # composite type
            default=NOT_PROVIDED,
            default_factory=None,
            doc=None,
        ),
        'synonym': CompositeInfo(
            # COMPLETELY copies the 'point' it points to!
            attribute_type=AttributeType.COMPOSITE,
            attribute=User.synonym,
            nullable=False,
            readable=True,
            writable=True,
            value_type=Point,
            default=NOT_PROVIDED,
            default_factory=None,
            doc=None,
        ),
        'articles_list': RelationshipInfo(
            attribute_type=AttributeType.RELATIONSHIP,
            attribute=User.articles_list,
            nullable=False,  # "no" when `uselist`
            readable=True,
            writable=True,
            value_type=List[Article],  # target model, collection
            target_model=Article,
            uselist=True,
            collection_class=list,
            default=NOT_PROVIDED,
            default_factory=list,
            doc=None,
        ),
        'articles_set': RelationshipInfo(
            attribute_type=AttributeType.RELATIONSHIP,
            attribute=User.articles_set,
            nullable=False,  # "no" when `uselist`
            readable=True,
            writable=False,  # `viewonly` is set
            value_type=Set[Article],  # target model, collection
            target_model=Article,
            uselist=True,
            collection_class=set,
            default=NOT_PROVIDED,
            default_factory=set,
            doc=None,
        ),
        'articles_dict_attr': RelationshipInfo(
            attribute_type=AttributeType.RELATIONSHIP,
            attribute=User.articles_dict_attr,
            nullable=False,  # "no" when `uselist`
            readable=True,
            writable=True,
            value_type=Dict[Any, Article],  # guessed the type!
            target_model=Article,
            uselist=True,
            collection_class=User.articles_dict_attr.property.collection_class,  # some weird class
            default=NOT_PROVIDED,
            default_factory=dict,
            doc=None,
        ),
        'articles_dict_keyfun': RelationshipInfo(
            attribute_type=AttributeType.RELATIONSHIP,
            attribute=User.articles_dict_keyfun,
            nullable=False,  # "no" when `uselist`
            readable=True,
            writable=True,
            value_type=Dict[Any, Article],  # guessed the type!
            target_model=Article,
            uselist=True,
            collection_class=User.articles_dict_keyfun.property.collection_class,  # some weird callable
            default=NOT_PROVIDED,
            default_factory=dict,
            doc=None,
        ),
        'article_titles': AssociationProxyInfo(
            attribute_type=AttributeType.ASSOCIATION_PROXY,
            attribute=User.article_titles,
            nullable=False,  # "yes" when `scalar`
            readable=True,
            writable=False,  # always false
            value_type=List[str],  # dict: target column's type, target model
            target_model=Article,
            collection_class=list,
            default=NOT_PROVIDED,
            default_factory=list,
            doc=None,
            target_attr_info=ColumnInfo(
                attribute_type=AttributeType.COLUMN,
                attribute=Article.title,
                primary_key=False,
                foreign_key=False,
                nullable=True,
                readable=True,
                writable=True,
                value_type=str,
                default=None,
                default_factory=None,
                doc=None
            ),
        ),
        'article_authors': AssociationProxyInfo(
            attribute_type=AttributeType.ASSOCIATION_PROXY,
            attribute=User.article_authors,
            nullable=False,
            readable=True,
            writable=False,  # always false
            value_type=List[User],  # dict: target column's type, target model
            target_model=Article,
            collection_class=list,
            default=NOT_PROVIDED,
            default_factory=list,
            doc=None,
            target_attr_info=RelationshipInfo(
                attribute_type=AttributeType.RELATIONSHIP,
                attribute=Article.user,
                nullable=True,
                readable=True,
                writable=True,
                value_type=User,
                target_model=User,
                uselist=False,
                collection_class=None,
                default=None,
                default_factory=None,
                doc=None,
            ),
        ),
        'articles_q': DynamicLoaderInfo(
            attribute_type=AttributeType.DYNAMIC_LOADER,
            attribute=User.articles_q,
            nullable=False,  # "no" when `uselist`
            readable=True,
            writable=True,  # yes it is!
            value_type=List[Article],  # target model, collection
            target_model=Article,
            uselist=True,
            collection_class=list,
            default=NOT_PROVIDED,
            default_factory=list,
            doc=None,
        ),
    }

    # Compare keys first
    assert set(generated_fields) == set(expected_fields)

    # Compare values
    if False:
        assert generated_fields == expected_fields
    # Compare values one by one
    # May be easier to debug when the difference is too large
    else:
        for k in generated_fields:
            assert (k, generated_fields[k]) == (k, expected_fields[k])

    # Compare final values
    assert {
        name: attr.final_value_type
        for name, attr in generated_fields.items()
    } == {
        '_ignored': Optional[str],
        'annotated_int': str,
        'int': Optional[int],
        'enum': Optional[EnumType],
        'optional': Optional[str],
        'required': str,
        'default': str,
        'documented': Optional[str],
        'json_attr': Optional[dict],
        'property_without_type': Any,  # note: `Any` is not wrapped into Optional[]
        'property_typed': str,
        'property_documented': Any,  # note: `Any` is not wrapped into Optional[]
        'property_nullable': Optional[str],
        'property_writable': str,
        'hybrid_property_typed': str,
        'hybrid_property_writable': str,
        'hybrid_method_attr': Any,
        'expression': Optional[int],
        'point': Point,
        'synonym': Point,
        'articles_list': List[Article],
        'articles_set': Set[Article],
        'articles_dict_attr': Dict[Any, Article],
        'articles_dict_keyfun': Dict[Any, Article],
        'article_titles': List[str],
        'article_authors': List[User],
        'articles_q': List[Article],
    }

    # Test sa_attribute_info()
    for attribute_name, expected_attribute_info in expected_fields.items():
        assert sa_attribute_info(User, attribute_name) == expected_attribute_info

    # Test primary key
    assert sa_model_primary_key_info(User) == {'annotated_int': expected_fields['annotated_int']}

    # Test sa_model_attributes_by_type()
    attrs_by_type = sa_model_attributes_by_type(User)

    assert set(attrs_by_type) == {
        type(attr_info) for attr_info in expected_fields.values()
    }

    assert attrs_by_type == {
        AttributeInfoType: {
            attr_name: attr_info
            for attr_name, attr_info in expected_fields.items()
            if type(attr_info) == AttributeInfoType  # don't use isinstance() because DynamicLoader will be part of relationship then
        }
        for AttributeInfoType in set(attrs_by_type)
    }


def test_sa_model_info_extractin__Article():
    """ Test sa_model_info(Article) """
    generated_fields = sa_model_info(Article, types=AttributeType.ALL, exclude=())
    expected_fields = {
        'id': ColumnInfo(
            attribute_type=AttributeType.COLUMN,
            attribute=Article.id,
            primary_key=True,
            foreign_key=False,
            nullable=False,  # primary key
            readable=True,
            writable=True,
            value_type=int,
            default=NOT_PROVIDED,  # because not nullable
            default_factory=None,
            doc=None
        ),
        'user_id': ColumnInfo(
            attribute_type=AttributeType.COLUMN,
            attribute=Article.user_id,
            primary_key=False,
            foreign_key=True,
            nullable=True,
            readable=True,
            writable=True,
            value_type=str,  # Note: gotten through a ForeinKey()
            default=None,  # because nullable
            default_factory=None,
            doc=None
        ),
        'title': ColumnInfo(
            attribute_type=AttributeType.COLUMN,
            attribute=Article.title,
            primary_key=False,
            foreign_key=False,
            nullable=True,
            readable=True,
            writable=True,
            value_type=str,
            default=None,  # because nullable
            default_factory=None,
            doc=None
        ),
        'user': RelationshipInfo(
            attribute_type=AttributeType.RELATIONSHIP,
            attribute=Article.user,
            nullable=True,  # singular
            readable=True,
            writable=True,
            value_type=User,  # not wrapped in any collections
            target_model=User,
            uselist=False,
            collection_class=None,
            default=None,  # because nullable
            default_factory=None,
            doc=None
        ),
    }

    assert generated_fields == expected_fields

    # Compare final values
    assert {
        name: attr.final_value_type
        for name, attr in generated_fields.items()
    } == {
        'id': int,
        'user_id': Optional[str],
        'title': Optional[str],
        'user': Optional[User],
    }

    # Test primary key
    assert sa_model_primary_key_info(Article) == {'id': expected_fields['id']}


def test_sa_model_info_extractin__Number():
    """ Test sa_model_info(Number): test for defaults """
    common_field_info = dict(
        attribute_type=AttributeType.COLUMN,
        primary_key=False,
        foreign_key=False,
        readable=True,
        writable=True,
        value_type=int,
        doc=None
    )

    generated_fields = sa_model_info(Number, types=AttributeType.ALL, exclude=())
    expected_fields = {
        'id': ColumnInfo(**{
            **common_field_info,
            **dict(
                attribute=Number.id,
                primary_key=True,
                nullable=False,  # primary key
                default=NOT_PROVIDED,  # because not nullable
                default_factory=None,
            ),
        }),
        'n': ColumnInfo(
            attribute=Number.n,
            nullable=True,  # nullable
            default=None,  # because nullable
            default_factory=None,
            **common_field_info
        ),
        'nd1': ColumnInfo(
            attribute=Number.nd1,
            nullable=True,
            default=100,
            default_factory=None,
            **common_field_info
        ),
        'nd2': ColumnInfo(
            attribute=Number.nd2,
            nullable=True,
            default=NOT_PROVIDED,  # we don't work with callables
            default_factory=None,
            **common_field_info
        ),
        'nd3': ColumnInfo(
            attribute=Number.nd3,
            nullable=True,
            default=NOT_PROVIDED,  # we don't work with expressions
            default_factory=None,
            **common_field_info
        ),
        'd1': ColumnInfo(
            attribute=Number.d1,
            nullable=False,
            default=100,
            default_factory=None,
            **common_field_info
        ),
        'd2': ColumnInfo(
            attribute=Number.d2,
            nullable=False,
            default=NOT_PROVIDED,  # we don't work with callables
            default_factory=None,
            **common_field_info
        ),
        'd3': ColumnInfo(
            attribute=Number.d3,
            nullable=False,
            default=NOT_PROVIDED,  # we don't work with expressions
            default_factory=None,
            **common_field_info
        ),
    }

    assert generated_fields == expected_fields


    # Test primary key
    assert sa_model_primary_key_info(Number) == {'id': expected_fields['id']}


def test_sa_model_info_extraction__JTI_Company():
    """ Test sa_model_info(JTI_Company) """
    generated_fields = sa_model_info(JTI_Company, types=AttributeType.ALL, exclude=())
    expected_fields = {
        'id': ColumnInfo(
            attribute_type=AttributeType.COLUMN,
            attribute=JTI_Company.id,
            primary_key=True,
            foreign_key=False,
            nullable=False,  # primary key
            readable=True,
            writable=True,
            value_type=int,
            default=NOT_PROVIDED,  # because not nullable
            default_factory=None,
            doc=None
        ),
        'name': ColumnInfo(
            attribute_type=AttributeType.COLUMN,
            attribute=JTI_Company.name,
            primary_key=False,
            foreign_key=False,
            nullable=True,
            readable=True,
            writable=True,
            value_type=str,
            default=None,
            default_factory=None,
            doc=None
        ),
        'employees': RelationshipInfo(
            attribute_type=AttributeType.RELATIONSHIP,
            attribute=JTI_Company.employees,
            nullable=False,
            readable=True,
            writable=True,
            value_type=List[JTI_Employee],
            target_model=JTI_Employee,
            uselist=True,
            collection_class=list,
            default=NOT_PROVIDED,
            default_factory=list,
            doc=None
        ),
    }

    assert generated_fields == expected_fields

    # Compare final values
    assert {
        name: attr.final_value_type
        for name, attr in generated_fields.items()
    } == {
        'id': int,
        'name': Optional[str],
        'employees': List[JTI_Employee],
    }


def test_sa_model_info_extraction__JTI_Employee():
    """ Test sa_model_info(JTI_Company) """
    generated_fields = sa_model_info(JTI_Employee, types=AttributeType.ALL, exclude=())
    assert set(generated_fields) == {
        'id', 'name', 'type', 'company_id', 'company',
    }
    assert generated_fields['company'] == RelationshipInfo(
        attribute_type=AttributeType.RELATIONSHIP,
        attribute=JTI_Employee.company,
        nullable=True,
        readable=True,
        writable=True,
        value_type=JTI_Company,
        target_model=JTI_Company,
        uselist=False,
        collection_class=None,
        default=None,
        default_factory=None,
        doc=None
    )

    # Engineer is the same: inherits fields
    generated_fields = sa_model_info(JTI_Engineer, types=AttributeType.ALL, exclude=())
    assert set(generated_fields) == {
        'id', 'name', 'type', 'company_id', 'company',  # inherited
        # plus one more field
        'engineer_name',
    }




def test_sa_model_info_extraction__STI_Employee():
    """ Test sa_model_info(STI_Employee) """
    assert set(sa_model_info(STI_Employee, types=AttributeType.ALL, exclude=())) == {
        'id', 'name', 'type',
    }

    assert set(sa_model_info(STI_Manager, types=AttributeType.ALL, exclude=())) == {
        'id', 'name', 'type',  # employee fields
        # additional fields
        'manager_data', 'company_id', 'company',
    }

    assert set(sa_model_info(STI_Engineer, types=AttributeType.ALL, exclude=())) == {
        'id', 'name', 'type',  # employee fields
        # additional fields
        'engineer_info',
    }



def test_sa_model_info_arguments():
    """ Test sa_model_info() targeting arguments """

    assert set(sa_model_info(User, types=AttributeType.COLUMN)) == {
        '_ignored', 'annotated_int', 'int', 'enum', 'optional', 'required', 'default', 'documented', 'json_attr',
    }

    assert set(sa_model_info(User, types=AttributeType.COLUMN, exclude=('int', 'enum', 'json_attr'))) == {
        '_ignored', 'annotated_int',                 'optional', 'required', 'default', 'documented',
    }

    assert set(sa_model_info(User, types=AttributeType.PROPERTY_R)) == {
        # only readable
        'property_without_type', 'property_typed', 'property_documented', 'property_nullable',
        'property_writable',  # both readable and writable
    }

    assert set(sa_model_info(User, types=AttributeType.PROPERTY_W)) == {
        # only writable
        'property_writable',  # fine selection
    }

    assert set(sa_model_info(User, types=AttributeType.PROPERTY_RW)) == {
        # both readable and writable
        'property_without_type', 'property_typed', 'property_documented', 'property_nullable', 'property_writable',
        'property_writable',
    }

    assert set(sa_model_info(User, types=AttributeType.HYBRID_PROPERTY_R)) == {
        'hybrid_property_typed', 'hybrid_property_writable',
    }

    assert set(sa_model_info(User, types=AttributeType.HYBRID_PROPERTY_W)) == {
        'hybrid_property_writable',
    }

    assert set(sa_model_info(User, types=AttributeType.HYBRID_PROPERTY_RW)) == {
        'hybrid_property_typed', 'hybrid_property_writable',
    }

    assert set(sa_model_info(User, types=AttributeType.RELATIONSHIP)) == {
        'articles_list', 'articles_set', 'articles_dict_attr', 'articles_dict_keyfun',
    }

    assert set(sa_model_info(User, types=AttributeType.DYNAMIC_LOADER)) == {
        'articles_q',
    }

    assert set(sa_model_info(User, types=AttributeType.ASSOCIATION_PROXY)) == {
        'article_titles', 'article_authors',
    }

    assert set(sa_model_info(User, types=AttributeType.COMPOSITE)) == {
        'point', 'synonym',
    }

    assert set(sa_model_info(User, types=AttributeType.EXPRESSION)) == {
        'expression',
    }

    assert set(sa_model_info(User, types=AttributeType.HYBRID_METHOD)) == {
        'hybrid_method_attr',
    }



