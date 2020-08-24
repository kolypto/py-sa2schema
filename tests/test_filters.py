from typing import Set

import pytest

import sa2schema as sa2
from sa2schema import AttributeType
from sa2schema.annotations import FilterT
from . import models


USER_PK = {'annotated_int'}
USER_COLUMNS = {
    '_ignored',
    'annotated_int', 'int', 'enum',
    'optional', 'required', 'default',
    'documented', 'json_attr',
}
USER_PROPS = {
    'property_without_type', 'property_typed', 'property_documented', 'property_nullable', 'property_writable',
}
USER_HPROPS = {
    'hybrid_property_typed', 'hybrid_property_writable', 'hybrid_method_attr',
}
USER_OTHER = {
    'expression', 'point', 'synonym',
}
USER_RELS = {
    'articles_list', 'articles_set', 'articles_dict_attr', 'articles_dict_keyfun', 'article_titles',
    'articles_q'
}
USER_ALL_FIELDS = USER_COLUMNS | USER_PROPS | USER_HPROPS | USER_OTHER | USER_RELS


@pytest.mark.parametrize(
    ('exclude', 'expected_fields'), [
        (
            sa2.filter.PRIMARY_KEY(),
            USER_ALL_FIELDS - USER_PK,
        ),
        (
            sa2.filter.ALL_BUT_PRIMARY_KEY(),
            USER_PK,
        ),
        (
            sa2.filter.READABLE,
            set(),
        ),
        (
            sa2.filter.WRITABLE,
            # only non-writable properties left
            (USER_PROPS | USER_HPROPS | {'article_titles', 'articles_set', 'expression'})
            - {'hybrid_property_writable', 'property_writable'}
        ),
        (
            sa2.filter.NULLABLE,
            USER_RELS | {
                'annotated_int', 'default', 'required', 'synonym',
                'hybrid_property_typed', 'hybrid_property_writable',
                'property_typed', 'property_writable',
                'point',
            },
        ),
        (
            sa2.filter.BY_TYPE(types=AttributeType.COLUMN),
            USER_ALL_FIELDS - USER_COLUMNS,
        ),
        (
            sa2.filter.BY_TYPE(types=AttributeType.COLUMN, attrs=['int']),
            USER_ALL_FIELDS - {'int'},
        ),
        (
            sa2.filter.NOT(['int']),
            {'int'},
        ),
        (
            sa2.filter.NOT(sa2.filter.PRIMARY_KEY),
            USER_PK,
        ),
        (
            sa2.filter.EITHER(
                sa2.filter.PRIMARY_KEY(),
                sa2.filter.BY_TYPE(types=AttributeType.ALL_RELATIONSHIPS | AttributeType.DYNAMIC_LOADER),
                ['_ignored'],
            ),
            USER_ALL_FIELDS - USER_PK - USER_RELS - {'_ignored'},
        ),
        (
            sa2.filter.NOT(
                sa2.filter.AND(
                    sa2.filter.BY_TYPE(types=AttributeType.PROPERTY_R),
                    sa2.filter.BY_TYPE(types=AttributeType.PROPERTY_W),
                ),
            ),
            {'property_writable'},
        ),
    ]
)
def test_field_filter(exclude: FilterT, expected_fields: Set[str]):
    model_info = sa2.sa_model_info(models.User,
                                   types=AttributeType.ALL,
                                   exclude=exclude)
    assert set(model_info) == set(expected_fields)
