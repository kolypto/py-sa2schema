from __future__ import annotations

from typing import Set, Union, Callable, Iterable

import sa2schema
from sa2schema.annotations import FilterT, FilterFunctionT, SAModelT, SAAttributeType


class FieldFilterBase:
    """ Base class for field filters

    A field filter is a callable that decides whether a particular field matches.
    """
    Model: SAModelT

    def for_model(self, Model: SAModelT):
        """ Bind the filter function to a model """
        self.Model = Model

    def __call__(self, name: str, attribute: SAAttributeType) -> bool:
        """ Filter function itself """
        raise NotImplementedError


class PRIMARY_KEY(FieldFilterBase):
    """ A filter that gives a positive to primary key fields

    Examples:
        exclude=PRIMARY_KEY()
        make_optional=PRIMARY_KEY()
    """
    primary_key_names: Set[str]

    def for_model(self, Model: SAModelT):
        super().for_model(Model)
        self.primary_key_names = set(sa2schema.sa_model_primary_key_names(Model))

    def __call__(self, name: str, attribute: SAAttributeType) -> bool:
        return name in self.primary_key_names


class ALL_BUT_PRIMARY_KEY(PRIMARY_KEY):
    """ A filter that gives a positive to fields that are not primary key fields

    Examples:
        exclude=ALL_BUT_PRIMARY_KEY()
        make_optional=ALL_BUT_PRIMARY_KEY()
    """
    def __call__(self, name: str, attribute: SAAttributeType) -> bool:
        return name not in self.primary_key_names


def prepare_filter_function(filter: FilterT, Model: SAModelT) -> FilterFunctionT:
    """ Convert the input to a proper filtering function

    * bool: becomes an all-matching or all-missing function
    * list of attribute names or attributes themselves
    * callable: used as is: callable(attribute-name, attribute)
    * FieldFilterBase: used as a filter
    """
    # True
    if filter is True:
        return lambda name, attr: True
    # False, None
    elif filter is None or filter is False:
        return lambda name, attr: False
    # FieldFilterBase()
    elif isinstance(filter, FieldFilterBase):
        filter.for_model(Model)
        return filter  # callable
    # FieldFilterBase() as a class
    elif isinstance(filter, type) and issubclass(filter, FieldFilterBase):
        return prepare_filter_function(filter(), Model)
    # Iterable
    elif isinstance(filter, Iterable):
        columns = ColumnsAndColumnNames(filter)
        return lambda name, attr: name in columns or attr in columns
    # Callable
    elif isinstance(filter, Callable):
        return filter
    # WAT?
    else:
        raise ValueError(filter)


class ColumnsAndColumnNames:
    """ A container that's able to handle both columns and column names, yet separately.

    Works both for columns, @property, and whatnot.

    Example:
        columns = ColumnsAndColumnNames(['name', User.age])

        'name' in columns  # -> True
        User.name in columns  # -> False

        'age' in columns  # -> False
        User.age in columns  # -> True
    """
    __slots__ = ('column_hashes', 'column_names')

    def __init__(self, items: Iterable[Union[str, SAAttributeType]]):
        column_names = []
        columns = []

        # Tell columns & names apart
        for item in items:
            if isinstance(item, str):
                column_names.append(item)
            else:
                columns.append(item)

        # Get ready
        self.column_hashes = frozenset(id(column) for column in columns)
        self.column_names = frozenset(column_names)

    def __contains__(self, item: Union[str, SAAttributeType]):
        if isinstance(item, str):
            return item in self.column_names
        else:
            return id(item) in self.column_hashes


