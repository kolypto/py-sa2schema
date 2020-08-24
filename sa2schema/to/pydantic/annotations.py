""" Annotations used here and there """

from typing import Union, Callable, TypeVar, Type

from pydantic import BaseModel
from sqlalchemy.ext.declarative import DeclarativeMeta

from sa2schema.annotations import SAModelT, SAAttributeType, FilterT, FilterFunctionT  # noqa
from sa2schema.compat import Literal  # noqa


# Pydantic Model class
PydanticModelT = TypeVar('PydanticModelT', bound=Type[BaseModel])


# A model naming maker function(Model)->str
# Returns the name for the model, used for forward references
ModelNameMakerFunction = Callable[[DeclarativeMeta], str]


# Model naming pattern: a template '{model}Db', or a callable
ModelNameMakerT = Union[str, ModelNameMakerFunction]
