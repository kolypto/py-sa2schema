""" sa_models() implementation that can work with many models that relate to one another

With sa_model() you can create singular models. However, if they have relationships, you'll need
to 1) hava all of them declared in the same module,
and 2) have a common naming scheme.
Then, when late binding is done, models find one another through the module's namespace.
"""

from functools import partial
from typing import Type, Optional, Mapping, Union

from pydantic import BaseModel

from sa2schema import AttributeType
from .annotations import PydanticModelT, SAModelT, ModelNameMakerT, FilterT
from .base_model import SAModel
from .sa_model import sa_model


class sa_models:
    """ A helper for models that can reference one another through relationships.

    Basically, it is a preset for sa_model() that makes sure that models will be able to find one another
    because they share a common python module and a naming scheme.

    Internally, it also works as a namespace which you can introspect.

    Example:
        # schemas.py
        from sa2schema import sa2
        from app.db import models  # SqlAlchemy models of your app
        ns = sa2.pydantic.sa_models(__name__, '{model}', types=AttributeType.RELATIONSHIP)
        User = ns.add(models.User)
        Article = ns.add(models.Article)
        ns.update_forward_refs()  # got to do it
    """

    def __init__(self,
                 module: str,
                 naming: ModelNameMakerT = '{model}',
                 *,
                 types: AttributeType = AttributeType.COLUMN,
                 Base: PydanticModelT = SAModel,
                 make_optional: FilterT = False,
                 only_readable: bool = False,
                 only_writable: bool = False,
                 ):
        """ Create a new group of models, all sharing a common naming pattern, and other attributes

        Args:
            module: The __name__ of the defining module.
                In fact, it is used by Pydantic as a namespace for related classes to find one another.
            naming: a '{model}Input' naming pattern, or a callable(Model)->str
            types: attribute types to include. See AttributeType
            Base: base Pydantic model to use. Can also use it to provide Config class
            make_optional: `True` to make all fields optional, or a list of fields/field names to make optional,
                            or a function(name) to select specific optional fields
                            Special case: `ALL_BUT_PRIMARY_KEY` will make all fields optional except for the primary key
            only_readable: only include fields that are readable. Useful for output models.
            only_writable: only include fields that are writable. Useful for input models.
        """
        # sa_model() as a partial
        self._sa_model = partial(
            sa_model,
            module=module,
            make_optional=make_optional,
            only_readable=only_readable,
            only_writable=only_writable,
            naming=naming
        )

        self._base = Base
        self._types = types

        # remember these models
        self._original_names: Mapping[str, BaseModel] = {}
        self._pydantic_names: Mapping[str, BaseModel] = {}

    def add(self,
            Model: Type[SAModelT],
            Parent: Optional[PydanticModelT] = None,
            *,
            types: AttributeType = AttributeType.NONE,
            exclude: FilterT = (),
            ) -> Type[BaseModel]:
        """ Add a model to the _pydantic_names

        Args:
            Model: the SqlAlchemy model to convert
            Parent: parent Pydantic model to use for for proper inheritance set up.
                Note that sa_model() won't detect inheritance automatically; you've got to do it yourself!!
            types: more types to add
            exclude: the list of fields to ignore, or a filter(name) to exclude fields dynamically.
                See also: sa2schema.filters for useful presets
        """
        model = self._sa_model(Model,
                               Parent=Parent or self._base,
                               types=self._types | types,
                               exclude=exclude)
        self._original_names[Model.__name__] = model
        self._pydantic_names[model.__name__] = model
        return model

    def update_forward_refs(self):
        """ Update forward references so that models point to one another """
        for model in self._pydantic_names.values():
            model.update_forward_refs(**self._pydantic_names)

    def __getattr__(self, model_name: str) -> BaseModel:
        """ Get a Pydantic model object by name """
        return self._original_names[model_name]

    def __iter__(self):
        """ List Pydantic models """
        return iter(self._original_names)

    def __contains__(self, model: Union[str, SAModelT]):
        """ Does this namespace contain the specific model?

        Args:
            model: Model name, or Model class
        """
        # Get the model name
        if isinstance(model, str):
            model_name = model
        elif isinstance(model, type):
            model_name = model.__name__
        else:
            raise ValueError(model)

        # Done
        return model_name in self._original_names
