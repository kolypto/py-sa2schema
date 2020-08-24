""" sa_model() implementation: converts from SqlAlchemy model to Pydantic model """
import typing
from typing import Tuple, Dict, Callable, Type, ForwardRef, Optional

from pydantic import BaseModel, create_model, Field, Required
from pydantic.fields import Undefined
from pydantic.typing import resolve_annotations
from sqlalchemy.ext.declarative import DeclarativeMeta

from sa2schema import filter
from sa2schema import sa_model_info
from sa2schema.attribute_info import AttributeInfo, RelationshipInfo, CompositeInfo, AssociationProxyInfo
from sa2schema.attribute_info import NOT_PROVIDED
from sa2schema.compat import get_origin, get_args
from sa2schema.defs import AttributeType
from .annotations import PydanticModelT, SAModelT, FilterT, FilterFunctionT, ModelNameMakerT, ModelNameMakerFunction
from .base_model import SAModel


def sa_model(Model: Type[SAModelT],
             Parent: PydanticModelT = SAModel,
             *,
             module: str = None,
             types: AttributeType = AttributeType.COLUMN,
             make_optional: FilterT = False,
             only_readable: bool = False,
             only_writable: bool = False,
             exclude: FilterT = (),
             naming: Optional[ModelNameMakerT] = None
             ) -> Type[BaseModel]:
    """ Create a Pydantic model from an SqlAlchemy model

    It will go through all attributes of the given SqlAlchemy model and use this information to create fields:
    attribute name, column type, its default value, nullability, and docstring.
    It can even extract the types of @property and @hybrid_property fields, if you've annotated their return types.

    If any attribute of the SqlAlchemy model has a type hint, it will be used instead of the column type.
    Use this approach if sa_model() guessed any of the types incorrectly.

    Note: it will ignore every field that starts with an underscore `_`.

    Args:
        Model: the SqlAlchemy model to convert
        Parent: base Pydantic model to use for a subclassed SqlAlchemy model.
            Note that sa_model() won't detect inheritance automatically; you've got to do it yourself!!
            Can also use it to provide Config class
        module: the module the model is going to be defined in.
            Be sure to set it when you use relationships! Weird errors may result if you don't.
        types: attribute types to include. See AttributeType
        make_optional: `True` to make all fields optional, or a list of fields/field names to make optional,
            or a function(name) to select specific optional fields.
            See also: sa2schema.filters for useful presets
        only_readable: only include fields that are readable. Useful for output models.
        only_writable: only include fields that are writable. Useful for input models.
        exclude: a list of fields/field names to ignore, or a filter(name) to exclude fields dynamically
        naming: naming pattern for models. Used to resolve forward references. One of:
            A string: something like '{model}Db', '{model}Input', '{model}Response'
            A callable(Model) to generate custom ForwardRef objects
            Note that if nothing's provided, you can't use relationships. How would they otherwise find each other?
    Returns:
        Pydantic model class
    """
    # prerequisites for handling relationships
    if types & (AttributeType.RELATIONSHIP | AttributeType.DYNAMIC_LOADER | AttributeType.ASSOCIATION_PROXY):
        if naming is None:
            raise ValueError("When using relationships, you need to provide a `naming`")
            # a `naming` function is absolutely essential.
            # Otherwise, how related classes will find each other?
        if not module:
            raise ValueError("When using relationships, you need to provide a `module`")
            # If you don't, __module__ won't be set on classes, and you will get really nasty errors,
            # like `KeyError(None)` on a line of code that doesn't do anything

    # naming
    naming = _prepare_naming_function(naming)

    # make_optional
    make_optional = filter.prepare_filter_function(make_optional, Model)

    # Create the model
    pd_model = create_model(
        __model_name=naming(Model),
        __module__=module,
        __base__=Parent,
        **sa_model_fields(Model, types=types,
                          exclude=exclude, make_optional=make_optional,
                          only_readable=only_readable,
                          only_writable=only_writable,
                          naming=naming
                          )
    )
    pd_model.__doc__ = Model.__doc__
    return pd_model


def sa_model_fields(Model: DeclarativeMeta, *,
                    types: AttributeType = AttributeType.COLUMN,
                    make_optional: FilterFunctionT,
                    only_readable: bool = False,
                    only_writable: bool = False,
                    exclude: FilterT = (),
                    can_omit_nullable: bool = True,
                    naming: ModelNameMakerFunction,
                    ) -> Dict[str, Tuple[type, Field]]:
    """ Take an SqlAlchemy model and generate pydantic Field()s from it

    It will use sa_model_info() to extract attribute information from the SqlAlchemy model.
    Only fields selected by `types` & `exclude` will be considered.
    If SqlAlchemy model contains type annotations, they will override column types.

    Args:
        Model: the model to generate fields from
        types: attribute types to include. See AttributeType
        make_optional: a function(name)->bool that selects fields to make Optional[]
        only_readable: only include fields that are readable
        only_writable: only include fields that are writable
        exclude: a list of fields/field names to ignore, or a filter(name, attribute) to exclude fields dynamically
        can_omit_nullable: `False` to make nullable fields and fields with defaults required.
        naming: optionally, a callable(Model) naming pattern generator. This is required for resolving relationship targets.
            If relationships aren't used, provide some exception thrower.
    Returns:
        a dict: attribute names => (type, Field)
    """
    # Model annotations will override any Column types
    model_annotations = getattr(Model, '__annotations__', {})
    model_annotations = resolve_annotations(model_annotations, Model.__module__)

    # Walk attributes and generate Field()s
    return {
        name: (
            # Field type
            pydantic_field_type(name, info, model_annotations, make_optional(name), naming),
            # Field() object
            make_field(info, can_omit_nullable=can_omit_nullable),
        )
        for name, info in sa_model_info(Model, types=types, exclude=exclude).items()
        if (not only_readable or info.readable) and
           (not only_writable or info.writable) and
           # Hardcoded for now.
           (not name.startswith('_'))  # exclude private properties. Consistent with Pydantic behavior.
    }


def make_field(attr_info: AttributeInfo,
               can_omit_nullable: bool = True,
               ) -> Field:
    """ Create a Pydantic Field() from an AttributeInfo """

    # Pydantic uses `Required = ...` to indicate which nullable fields are required
    # `Undefined` for nullable fields will result in `None` being the default
    no_default = Undefined if can_omit_nullable else Required

    # Generate fields
    return Field(
        # Use the default.
        # If no default... it's either optional or required, depending on `can_omit_nullable`
        default=no_default
                if attr_info.default is NOT_PROVIDED else
                attr_info.default,
        default_factory=attr_info.default_factory,
        alias=None,  # sqlalchemy synonyms are installed later on
        title=attr_info.doc,  # `title` seems fine. `description` can be used for more verbose stuff
    )


def pydantic_field_type(attr_name: str,
                        attr_info: AttributeInfo,
                        model_annotations: Dict[str, type],
                        make_optional: bool,
                        naming: ModelNameMakerT,
                        ) -> type:
    """ Choose a field type for pydantic """
    # For relationships, we use the naming() generator to generate a name, make a ForwardRef, and replace the model
    if isinstance(attr_info, (RelationshipInfo, AssociationProxyInfo)) and naming:
        attr_info = attr_info.replace_model(
            ForwardRef(naming(attr_info.target_model))
        )
    # For composites, we replace them by name, straight.
    if isinstance(attr_info, CompositeInfo):
        attr_info = attr_info.replace_value_type(
            ForwardRef(attr_info.value_type.__name__)
        )

    # Get the type

    # If a model annotation is given, use it
    if attr_name in model_annotations:
        type_ = model_annotations[attr_name]
        # replace SqlAlchemy models with forward refs
        type_ = _replace_models_with_forward_references(type_, naming)
    # If a type is not overridden in annotations, take one from the attribute
    else:
        # In case it referenced other models, replacements have already been made
        type_ = attr_info.final_value_type

    # make_optional?
    if make_optional:
        type_ = Optional[type_]

    # Done
    return type_


def _replace_models_with_forward_references(type_: Type, naming: ModelNameMakerFunction) -> Type:
    """ Walk the arguments of `type_` and replace every possible reference to any SqlAlchemy model """
    # SqlAlchemy model
    if isinstance(type_, DeclarativeMeta):
        return ForwardRef(naming(type_))
    # typing.Optional[], typing.Union[], and other subscriptable types
    elif isinstance(type_, typing._GenericAlias):
        # type_: List[models.User]
        # original_type: list
        # original_args: (models.User,)
        original_type, type_args = get_origin(type_), get_args(type_)

        # try to normalize it:
        # convert type_=list to type_=typing.List
        try:
            original_type = getattr(
                typing,
                typing._normalize_alias[original_type.__name__]
            )
        except (KeyError, AttributeError) as e:
            pass

        # Recurse: convert every argument
        arghs = tuple(
            _replace_models_with_forward_references(t, naming)
            for t in type_args
        )

        # Reconstruct
        return original_type[arghs]
    else:
        return type_



def _prepare_naming_function(naming: Optional[ModelNameMakerT]) -> ModelNameMakerFunction:
    """ Given the `naming` argument, convert it into a guaranteed Optional[callable]

    If the argument is a function, leave it as it is.
    If the argument is a string, treat it like '{model}Input' pattern, and make a ForwardRef from it.
    Otherwise, do nothing: return as it is.
    """
    # If a string is given, it's a pattern
    if isinstance(naming, str):
        assert '{model' in naming, 'The `naming` string must contain a reference to {model}'
        return lambda model: naming.format(model=model.__name__)
    # `None` is acceptable
    elif naming is None:
        return lambda model: model.__name__
    # Callable is ok
    elif isinstance(naming, Callable):
        return naming
    # Complain
    else:
        raise ValueError(naming)
