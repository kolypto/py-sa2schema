""" SA-Pydantic bridge between SqlAlchemy and Pydantic """
from functools import partial
from typing import TypeVar, Tuple, Dict, Union, Callable, Type, ForwardRef, Optional
from pydantic.fields import Undefined
from pydantic import BaseModel, BaseConfig, create_model, Field, Required
from sqlalchemy.ext.declarative import DeclarativeMeta

from sa2schema import AttributeType, sa_model_info
from sa2schema.sa_extract_info import ExcludeFilterT
from sa2schema.attribute_info import NOT_PROVIDED
from sa2schema.attribute_info import AttributeInfo, RelationshipInfo, CompositeInfo, AssociationProxyInfo


class SAModel(BaseModel):
    """ Base for SqlAlchemy models """

    class Config(BaseConfig):
        # Enabling orm_mode makes pydantic pick attributes of objects when necessary
        orm_mode = True


# Model class
ModelT = TypeVar('ModelT')


# A forward reference generator function
ForwardRefGeneratorT = Callable[[DeclarativeMeta], str]


class Group:
    """ A group of models related to one another.

    For instance, a group of DB models, a group of input models, a group of output models.

    A Group() is nothing mode than a partial(sa_model) that feeds the same `module` and `forwardref`.
    This way, every model will have a common forward-reference pattern and be able to find one another.

    In addition to that, it remembers every model in its `.namespace` attribute,
    through which these forward references are resolved.
    """

    def __init__(self,
                 module: str,
                 forwardref: Union[str, ForwardRefGeneratorT],
                 *,
                 types: AttributeType = AttributeType.COLUMN,
                 only_readable: bool = False,
                 only_writable: bool = False,
                 ):
        """ Create a new group of models, all sharing a common naming pattern, and other attributes

        Args:
            module: The __name__ of the defining module
            forwardref: a '{model}Input' pattern, or a callable(Model)->ForwardRef
            types: attribute types to include. See AttributeType
            only_readable: only include fields that are readable. Useful for output models.
            only_writable: only include fields that are writable. Useful for input models.
        """
        # sa_model() as a partial
        self._sa_model = partial(
            sa_model,
            module=module,
            only_readable=only_readable,
            only_writable=only_writable,
            forwardref=forwardref
        )

        self._types = types

        # remember these models
        self.namespace = {}

    def sa_model(self,
                 Model: DeclarativeMeta,
                 Parent: Type[ModelT] = SAModel,
                 types: AttributeType = AttributeType.NONE,
                 exclude: ExcludeFilterT = (),
                 ) -> Type[ModelT]:
        """ Add a model to the group

        Args:
            Model: the SqlAlchemy model to convert
            Parent: base Pydantic model to use for a subclassed SqlAlchemy model.
                Note that sa_model() won't detect inheritance automatically; you've got to do it yourself!!
                Can also use it to provide Config class
            types: more types
            exclude: the list of fields to ignore, or a filter(name, attribute) to exclude fields dynamically
        """
        model = self._sa_model(Model, Parent, exclude=exclude, types=self._types | types)
        self.namespace[model.__name__] = model
        return model

    def update_forward_refs(self):
        """ Update forward references so that models point to one another """
        for model in self.namespace.values():
            model.update_forward_refs(**self.namespace)


def sa_model(Model: DeclarativeMeta,
             Parent: Type[ModelT] = SAModel,
             *,
             module: str = None,
             types: AttributeType = AttributeType.COLUMN,
             only_readable: bool = False,
             only_writable: bool = False,
             exclude: ExcludeFilterT = (),
             forwardref: Union[str, ForwardRefGeneratorT] = None
             ) -> Type[ModelT]:
    """ Create a Pydantic model from an SqlAlchemy model

    It will go through all attributes of the given SqlAlchemy model and use this information to create fields:
    attribute name, column type, its default value, nullability, and docstring.
    It can even extract the types of @property and @hybrid_property fields, if you've annotated their return types.

    If any attribute of the SqlAlchemy model has a type hint, it will be used instead of the column type.
    Use this approach if sa_model() guessed any of the types incorrectly.

    Args:
        Model: the SqlAlchemy model to convert
        Parent: base Pydantic model to use for a subclassed SqlAlchemy model.
            Note that sa_model() won't detect inheritance automatically; you've got to do it yourself!!
            Can also use it to provide Config class
        module: the module the model is going to be defined in.
            Be sure to set it when you use relationships! Weird errors may result if you don't.
        types: attribute types to include. See AttributeType
        only_readable: only include fields that are readable. Useful for output models.
        only_writable: only include fields that are writable. Useful for input models.
        exclude: the list of fields to ignore, or a filter(name, attribute) to exclude fields dynamically
        forwardref: pattern for forward references to models. Can be:
            A string: something like '{model}Db', '{model}Input', '{model}Response'
            A callable(Model) to generate custom ForwardRef objects
            Note that if nothing's provided, you can't use relationships. How would they otherwise find each other?
    Returns:
        Pydantic model class
    """
    # prerequisites for handling relationships
    if types & (AttributeType.RELATIONSHIP | AttributeType.DYNAMIC_LOADER | AttributeType.ASSOCIATION_PROXY):
        if forwardref is None:
            raise ValueError("When using relationships, you need to provide a `forwardref`")
            # a `forwardref` function is absolutely essential.
            # Otherwise, how related classes will find each other?
        if not module:
            raise ValueError("When using relationships, you need to provide a `module`")
            # If you don't, __module__ won't be set on classes, and you will get really nasty errors,
            # like `KeyError(None)` on a line of code that doesn't do anything

    # forwardref
    forwardref = prepare_forwardref_function(forwardref)

    # Create the model
    pd_model = create_model(
        __model_name=generate_model_name(Model, forwardref),
        __module__=module,
        __base__=Parent,
        **sa_model_fields(Model, types=types, exclude=exclude,
                          only_readable=only_readable,
                          only_writable=only_writable,
                          forwardref=forwardref
                          )
    )
    pd_model.__doc__ = Model.__doc__
    return pd_model


def sa_model_fields(Model: DeclarativeMeta, *,
                    types: AttributeType = AttributeType.COLUMN,
                    only_readable: bool = False,
                    only_writable: bool = False,
                    exclude: ExcludeFilterT = (),
                    can_omit_nullable: bool = True,
                    forwardref: Optional[ForwardRefGeneratorT],
                    ) -> Dict[str, Tuple[type, Field]]:
    """ Take an SqlAlchemy model and generate pydantic Field()s from it

    It will use sa_model_info() to extract attribute information from the SqlAlchemy model.
    Only fields selected by `types` & `exclude` will be considered.
    If SqlAlchemy model contains type annotations, they will override column types.

    Args:
        Model: the model to generate fields from
        types: attribute types to include. See AttributeType
        only_readable: only include fields that are readable
        only_writable: only include fields that are writable
        exclude: the list of fields to ignore, or a filter(name, attribute) to exclude fields dynamically
        can_omit_nullable: `False` to make nullable fields and fields with defaults required.
        forwardref: optionally, a callable(Model) able to generate a forward reference.
            This is required for resolving relationship targets.
            If relationships aren't used, provide some exception thrower.
            If None, no relationship will be replaced with a forward reference.
    Returns:
        a dict: attribute names => (type, Field)
    """
    # Model annotations will override any Column types
    model_annotations = getattr(Model, '__annotations__', {})

    # Walk attributes and generate Field()s
    return {
        name: (
            # Field type
            pydantic_field_type(name, info, model_annotations, forwardref),
            # Field() object
            make_field(info, can_omit_nullable),
        )
        for name, info in sa_model_info(Model, types=types, exclude=exclude).items()
        if (not only_readable or info.readable) and
           (not only_writable or info.writable)
    }


def make_field(attr_info: AttributeInfo,
               can_omit_nullable: bool=True,
               ) -> Field:
    """ Create a Pydantic Field() from an AttributeInfo """

    # Pydantic uses `Required = ...` to indicate which nullable fields are required
    # `Undefined` for nullable fields will result in `None` being the default
    no_default = Undefined if can_omit_nullable else Required
    return Field(
        default=no_default
                if attr_info.default is NOT_PROVIDED else
                attr_info.default,
        alias=None,  # sqlalchemy synonyms are installed later on
        title=attr_info.doc,  # `title` seems fine. `description` can be used for more verbose stuff
    )


def generate_model_name(Model: DeclarativeMeta, forwardref: Optional[ForwardRefGeneratorT]) -> str:
    """ Generate a name for the model """
    if forwardref:
        return forwardref(Model)
    else:
        return Model.__name__


def prepare_forwardref_function(forwardref: Optional[Union[ForwardRefGeneratorT, str]]) -> Optional[ForwardRefGeneratorT]:
    """ Create a forward reference generator function

    If the argument is a function, leave it as it is.
    If the argument is a string, treat it like '{model}Input' pattern, and get a ForwardRef from it.
    Otherwise, do nothing: return as it is.
    """
    # If a string is given, it's a pattern
    if isinstance(forwardref, str):
        forwardref_str = forwardref
        assert '{model' in forwardref_str, 'The `forwardref` string must contain a reference to {model}'
        return lambda model: forwardref_str.format(model=model.__name__)

    # Otherwise, return as is
    return forwardref


def pydantic_field_type(attr_name: str,
                        attr_info: AttributeInfo,
                        model_annotations: Dict[str, type],
                        forwardref: Optional[ForwardRefGeneratorT],
                        ):
    """ Choose a field type for pydantic """
    # For relationships, we use the forwardref() generator to replace it with a forward reference
    if isinstance(attr_info, (RelationshipInfo, AssociationProxyInfo)) and forwardref:
        attr_info = attr_info.replace_model(
            ForwardRef(forwardref(attr_info.target_model))
        )
    # For composites, we replace them by name, straight.
    if isinstance(attr_info, CompositeInfo):
        attr_info = attr_info.replace_value_type(
            ForwardRef(attr_info.value_type.__name__)
        )

    # Done
    return model_annotations.get(
        # try to get the type override
        attr_name,
        # fall back to annotation types
        attr_info.final_value_type
    )

