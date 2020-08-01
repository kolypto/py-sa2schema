""" Models: container for models that can relate to one another """


from functools import partial
from typing import Type, Optional

from pydantic import BaseModel

from sa2schema import AttributeType
from sa2schema.sa_extract_info import ExcludeFilterT

from .annotations import ModelT, SAModelT, ForwardRefGeneratorT, MakeOptionalFilterT
from .base_model import SAModel
from .sa_model import sa_model


class Models:
    """ A container for models that can relate to one another.

    For instance, a group of DB models, a group of input models, a group of output models.

    A Namespace() is nothing mode than a partial(sa_model) that feeds the same `module` and `forwardref`.
    This way, every model will have a common forward-reference pattern and be able to find one another.

    In addition to that, it remembers every model in its `.namespace` attribute,
    through which these forward references are resolved.

    Example:
        >>> # schemas.py
        >>> from sa2schema import sa2
        >>> from app.db import models  # SqlAlchemy models of your app
        >>> ns = sa2.pydantic.Models(__name__, '{model}', types=AttributeType.RELATIONSHIP)
        >>> User = ns.sa_model(models.User)
        >>> Article = ns.sa_model(models.Article)
        >>> ns.update_forward_refs()  # got to do it
    """

    def __init__(self,
                 module: str,
                 forwardref: ForwardRefGeneratorT = '{model}',
                 *,
                 types: AttributeType = AttributeType.COLUMN,
                 Base: Type[ModelT] = SAModel,
                 make_optional: MakeOptionalFilterT = False,
                 only_readable: bool = False,
                 only_writable: bool = False,
                 ):
        """ Create a new group of models, all sharing a common naming pattern, and other attributes

        Args:
            module: The __name__ of the defining module
            forwardref: a '{model}Input' pattern, or a callable(Model)->ForwardRef
            types: attribute types to include. See AttributeType
            Base: base Pydantic model to use. Can also use it to provide Config class
            make_optional: `True` to make all fields optional, or a list of fields/field names to make optional,
                            or a function(name, attribute) to select specific optional fields
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
            forwardref=forwardref
        )

        self._base = Base
        self._types = types

        # remember these models
        self.namespace = {}

    def sa_model(self,
                 Model: Type[SAModelT],
                 Parent: Optional[Type[ModelT]] = None,
                 *,
                 types: AttributeType = AttributeType.NONE,
                 exclude: ExcludeFilterT = (),
                 ) -> Type[BaseModel]:
        """ Add a model to the namespace

        Args:
            Model: the SqlAlchemy model to convert
            Parent: parent Pydantic model to use for for proper inheritance set up.
                Note that sa_model() won't detect inheritance automatically; you've got to do it yourself!!
            types: more types to add
            exclude: a list of fields/field names to ignore, or a filter(name, attribute) to exclude fields dynamically
        """
        model = self._sa_model(Model,
                               Parent=Parent or self._base,
                               types=self._types | types,
                               exclude=exclude)
        self.namespace[model.__name__] = model
        return model

    def update_forward_refs(self):
        """ Update forward references so that models point to one another """
        for model in self.namespace.values():
            model.update_forward_refs(**self.namespace)
