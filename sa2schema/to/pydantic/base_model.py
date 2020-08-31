""" Implementations of Pydantic BaseModel: for all models that depend on SqlAlchemy """
from typing import Type, Optional

from pydantic import BaseModel, BaseConfig, Extra
from pydantic.utils import GetterDict

from sa2schema.pluck import PluckMap, sa_pluck
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


    @classmethod
    def from_orm(cls: PydanticModelT, obj: SAModelT, pluck: Optional[PluckMap] = None) -> PydanticModelT:
        """ Create a Pydantic model from an ORM object

        NOTE: this function is most efficient when used with an explicit `pluck` map. See sa_pluck()
        This is because from_orm() uses a GetterDict wrapper which adds overhead to every unloaded attribute.

        NOTE: it will fail if your model has required fields and `pluck` excludes them.
        Plucking only works well with partial models.

        Args:
            obj: The SqlAlchemy instance to create the Pydantic model from
            pluck: The pluck map. See sa_pluck()
        """
        # Best case: pluck map is given
        if pluck is not None:
            d = sa_pluck(obj, pluck)
            return cls.parse_obj(d)

        # super
        return super().from_orm(obj)


class SALoadedModel(SAModel):
    """ Base for SqlAlchemy models that will only return attributes that are already loaded.

    Unloaded attributes will have `None` as their values.
    Use with `make_optional`: otherwise, you'll get many "can't be None" errors
    """

    class Config(SAModel.Config):
        # GetterDict that won't trigger the loading of any attributes
        getter_dict = SALoadedGetterDict

    @classmethod
    def from_orm(cls: PydanticModelT, obj: SAModelT, pluck: Optional[PluckMap] = None) -> PydanticModelT:
        res = super().from_orm(obj, pluck)

        # Unset unloaded fields
        # (but don't do it when `pluck` is provided, because such an object will be perfect already)
        if res is not None and pluck is None:
            # NOTE: SALoadedGetterDict has decided to exclude some fields, but it was unable to update __fields_set__
            # Therefore, we have to do it here.
            # Why we have to do it here? Because GetterDict has no access to the Pydantic model.
            # Why do it at all? Because otherwise unloaded attributes will look like they have `None`s from the DB;
            # but because of __fields_set__, we can leverage BaseModel.dict(exclude_unset=True)
            excluded = SALoadedGetterDict.get_names_excluded_from(obj)
            res.__fields_set__.difference_update(excluded)

        # Done
        return res
