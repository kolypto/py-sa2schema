""" Annotations used here and there """

from typing import TypeVar, Union, Callable, Type, Iterable

from pydantic import BaseModel
from sqlalchemy.ext.declarative import DeclarativeMeta

from sa2schema.compat import Literal
from sa2schema.sa_extract_info import SAAttributeType

# SqlAlchemyModel
SAModelT = TypeVar('SAModelT', bound=DeclarativeMeta)


# Pydantic Model class
ModelT = TypeVar('ModelT', bound=Type[BaseModel])


# A callable to choose fields for making them Optional[]
# Returns `True` to make the field optional, `False` to leave it as it is
MakeOptionalFilterFunction = Callable[[str, SAAttributeType], bool]


# A filter to choose which fields to make Optional[]:
# a function, or a set of field names, or `True` to make all of them optional
MakeOptionalFilterT = Union[bool, Iterable[str], MakeOptionalFilterFunction]


# A forward reference generator function(Model)->str
# Returns the name for the forward reference
ForwardRefGeneratorFunction = Callable[[DeclarativeMeta], str]


# Forward reference pattern: a template '{model}Db', or a callable
ForwardRefGeneratorT = Union[str, ForwardRefGeneratorFunction]
