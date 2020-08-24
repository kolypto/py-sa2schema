""" Implementations of Pydantic BaseModel: for all models that depend on SqlAlchemy """
from typing import Type, Mapping

from pydantic import BaseModel, BaseConfig, Extra
from pydantic.utils import GetterDict

from .annotations import PydanticModelT, SAModelT
from .base_model_recursion import NoneRecursiveParserMixin
from .getter_dict import SAGetterDict, SALoadedGetterDict


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

    Unloaded attributes will have `None` as their values.
    Use with `make_optional`: otherwise, you'll get many "can't be None" errors
    """

    class Config(SAModel.Config):
        # GetterDict that won't trigger the loading of any attributes
        getter_dict = SALoadedGetterDict

    @classmethod
    def from_orm(cls: PydanticModelT, obj: SAModelT, pluck: Mapping[str, bool] = None) -> PydanticModelT:
        if pluck:
            raise NotImplementedError  # TODO: implement. How? Perhaps, keep a stack of objects using Session.info?

        # Convert
        res = super().from_orm(obj)

        # Unset unloaded fields
        if res is not None:
            # NOTE: SALoadedGetterDict has decided to exclude some fields, but it was unable to update __fields_set__
            # Therefore, we have to do it here.
            # Why we have to do it here? Because GetterDict has no access to the Pydantic model.
            # Why do it at all? Because otherwise unloaded attributes will look like they have `None`s from the DB;
            # but because of __fields_set__, we can leverage BaseModel.dict(exclude_unset=True)
            excluded = SALoadedGetterDict.get_names_excluded_from(obj)
            res.__fields_set__.difference_update(excluded)

        # Done
        return res
