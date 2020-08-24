""" Annotations used here and there """

from typing import TypeVar, Union, Callable, Type, Iterable

from pydantic import BaseModel
from sqlalchemy.ext.declarative import DeclarativeMeta
from sqlalchemy.ext.hybrid import hybrid_property, hybrid_method
from sqlalchemy.orm.attributes import InstrumentedAttribute, QueryableAttribute

from sa2schema.compat import Literal  # noqa


# SqlAlchemyModel
SAModelT = TypeVar('SAModelT', bound=DeclarativeMeta)


# SqlAlchemy attributes
SAAttributeType = Union[InstrumentedAttribute, QueryableAttribute, property, hybrid_property, hybrid_method]


# Pydantic Model class
ModelT = TypeVar('ModelT', bound=Type[BaseModel])


# A filter function that decides whether a certain field matches
# function(field-name, attribute-object) -> bool
# return `True` to match a field, `False` to miss it.
FilterFunctionT = Callable[[str, SAAttributeType], bool]

# Field filter:
# * bool
# * a list of field names
# * a list of columns
# * a callable
# * an instance of FieldFilterBase
FilterT = Union[bool, Iterable[str], Iterable[SAAttributeType], FilterFunctionT, 'FieldFilterBase']

