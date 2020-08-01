""" Implementations of Pydantic BaseModel: for all models that depend on SqlAlchemy """
from typing import Type

from pydantic import BaseModel, BaseConfig, Extra
from pydantic.utils import GetterDict

from .getter_dict import SAGetterDict, SALoadedGetterDict
from .base_model_recursion import NoneRecursiveParserMixin


class SAModel(NoneRecursiveParserMixin, BaseModel):
    """ Base for SqlAlchemy models.

    This model will brutely load all unloaded attributes, even if that triggers hundreds of additional SQL queries.

    When encountering recursive relationships, it will replace their recursive values with `None`. Make sure your schema is ready for that.
    Use it with `make_optional`; that's the best thing.
    """

    class Config(BaseConfig):
        # Enabling orm_mode makes Pydantic pick attributes of objects when necessary
        orm_mode = True

        # Custom GetterDict
        getter_dict: Type[GetterDict] = SAGetterDict

        # Forbid extra attributes
        extra = Extra.forbid


class SALoadedModel(SAModel):
    """ Base for SqlAlchemy models that will only return attributes that are already loaded.

    This model will only contain attributes which were already loaded.
    Unloaded attributes will be set to `None`.
    Use with `make_optional`: otherwise, you'll get many "can't be None" errors
    """

    class Config(SAModel.Config):
        # GetterDict that won't trigger the loading of any attributes
        getter_dict = SALoadedGetterDict
