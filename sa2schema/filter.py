""" Filter presets for `exclude` and `make_optional`

Examples:
    exclude=ALL_BUT_PRIMARY_KEY
    make_optional=ALL_BUT_PRIMARY_KEY
"""

from __future__ import annotations

from typing import Set, Callable, Iterable

import sa2schema
from sa2schema.annotations import FilterT, FilterFunctionT, SAModelT
from sa2schema.defs import AttributeType


class FieldFilterBase:
    """ Base class for field filters

    A field filter is a callable that decides whether a particular field matches.
    """
    Model: SAModelT

    def for_model(self, Model: SAModelT):
        """ Bind the filter function to a model """
        self.Model = Model

    def __call__(self, name: str) -> bool:
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

    def __call__(self, name: str) -> bool:
        return name in self.primary_key_names


class ALL_BUT_PRIMARY_KEY(PRIMARY_KEY):
    """ A filter that gives a positive to fields that are not primary key fields

    Examples:
        exclude=ALL_BUT_PRIMARY_KEY()
        make_optional=ALL_BUT_PRIMARY_KEY()
    """
    def __call__(self, name: str) -> bool:
        return name not in self.primary_key_names


class READABLE(FieldFilterBase):
    """ A filter that selects only redable attributes

    Example:
        make_optional=READABLE
    """
    def for_model(self, Model: SAModelT):
        super().for_model(Model)
        self.model_info = sa2schema.sa_model_info(Model, types=AttributeType.ALL)

    def __call__(self, name: str) -> bool:
        return self.model_info[name].readable


class WRITABLE(READABLE):
    """ A filter that selects only redable attributes

    Example:
        exclude=WRITABLE
    """
    def __call__(self, name: str) -> bool:
        return self.model_info[name].writable


class NULLABLE(READABLE):
    """ A filter that selects only nullable attributes

    Example:
        exclude=NULLABLE
    """
    def __call__(self, name: str) -> bool:
        return self.model_info[name].nullable


class BY_TYPE(FieldFilterBase):
    """ A filter that selects attributes by type AND by names

    NOTE: `attrs` may be a list of names, or another filtering expression

    Example:
        exclude = BY_TYPE(types=AttributeType.RELATIONSHIP, include=[''])
    """
    def __init__(self, *, types: AttributeType, attrs: FilterT = True):
        self.types = types
        self.exclude = NOT(attrs)

    def for_model(self, Model: SAModelT):
        super().for_model(Model)
        self.model_info = sa2schema.sa_model_info(Model, types=self.types, exclude=self.exclude)

    def __call__(self, name: str) -> bool:
        # `model_info` already
        return name in self.model_info


class EITHER(FieldFilterBase):
    """ A predicate that composes multiple other filters.

    If any of them matches, the attributes is a match.

    Examples:
        exclude=EITHER(
            ['name', 'age'],
            BY_TYPE(types=AttributeType.RELATIONSHIP)
        )
    """
    def __init__(self, *filters):
        self.filters = filters

    def for_model(self, Model: SAModelT):
        super().for_model(Model)
        self.prepared_filters = [
            prepare_filter_function(filter, self.Model)
            for filter in self.filters
        ]

    def __call__(self, name: str) -> bool:
        return any(
            filter(name)
            for filter in self.prepared_filters
        )


class AND(EITHER):
    """ A predicate that composes multiple other filters

    An attribute only matches if all filters match.

    Examples:
        exclude=AND()
    """
    def __call__(self, name: str) -> bool:
        return all(
            filter(name)
            for filter in self.prepared_filters
        )


class NOT(AND):
    """ A predicate that negates another filter

    An attribute only matches if the filter didn't like it

    Examples:
        exclude=NOT(['password'])
    """
    def __call__(self, name: str) -> bool:
        return not super().__call__(name)



def prepare_filter_function(filter: FilterT, Model: SAModelT) -> FilterFunctionT:
    """ Convert the input to a proper filtering function

    * bool: becomes an all-matching or all-missing function
    * list of attribute names
    * callable: used as is: callable(attribute-name, attribute)
    * FieldFilterBase: used as a filter
    """
    # True
    if filter is True:
        return lambda name: True
    # False, None
    elif filter is None or filter is False:
        return lambda name: False
    # FieldFilterBase()
    elif isinstance(filter, FieldFilterBase):
        filter.for_model(Model)
        return filter  # callable
    # FieldFilterBase() as a class
    elif isinstance(filter, type) and issubclass(filter, FieldFilterBase):
        return prepare_filter_function(filter(), Model)
    # Iterable
    elif isinstance(filter, Iterable):
        column_names = set(filter)
        return lambda name: name in column_names
    # Callable
    elif isinstance(filter, Callable):
        return filter
    # WAT?
    else:
        raise ValueError(filter)

