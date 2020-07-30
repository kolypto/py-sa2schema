""" SA-Pydantic bridge between SqlAlchemy and Pydantic """

from functools import partial
from typing import TypeVar, Tuple, Dict, Union, Callable, Type, ForwardRef, Optional, Iterable, Iterator, Any, Set
from pydantic.fields import Undefined
from pydantic import BaseModel, BaseConfig, create_model, Field, Required, Extra
from pydantic.utils import GetterDict
from sqlalchemy import inspect
from sqlalchemy.ext.declarative import DeclarativeMeta
from sqlalchemy.orm.base import instance_state
from sqlalchemy.orm.state import InstanceState

from sa2schema import AttributeType, sa_model_info
from sa2schema.sa_extract_info import all_sqlalchemy_model_attribute_names
from sa2schema.sa_extract_info import ExcludeFilterT, SAAttributeType, _ColumnsOrColumnNames
from sa2schema.attribute_info import NOT_PROVIDED
from sa2schema.attribute_info import AttributeInfo, RelationshipInfo, CompositeInfo, AssociationProxyInfo
from sa2schema.attribute_info import Literal  # compatibility is there


# TODO: remake into a `pydantic` model, split into files


class SAGetterDict(GetterDict):
    """ Adapter that extracts data from SqlAlchemy models

    It knows all the attributes and properties
    """

    # re-implement every method that refers to self._obj

    def __iter__(self) -> Iterator[str]:
        # Get the list of attribute names from the model itself, not from the object
        # Why? because otherwise we will miss @property attributes, and they just might be useful
        return iter(all_sqlalchemy_model_attribute_names(type(self._obj)))

    # other methods (get(), __getitem__()) are fine


class SALoadedGetterDict(SAGetterDict):
    """ Adapter that extracts only the loaded data from SqlAlchemy models

    The advantage of this GetterDict is that it will never trigger loading of any SqlAlchemy
    attributes that aren't loaded.

    Be careful, though: if a field isn't loaded, this getter will return a None,
    which might not always make sense to your application.
    """
    __slots__ = ('_unloaded',)

    #: const: the value to return for unloaded attributes
    #: Note that the very same value will be used for collections as well.
    #: NOTE: set it to `pydantic.main._missing` and Pydantic will return Field defaults instead.
    #: see: validate_model()
    EMPTY_VALUE = None

    #: Cached set of unloaded attributes.
    #: We cache it because it's not supposed to be modified while we're iterating the model
    _unloaded: Set[str]

    def __init__(self, obj: Any):
        super().__init__(obj)

        # Make a list of attributes the loading of which would lead to an unwanted DB query
        state: InstanceState = instance_state(self._obj)
        self._unloaded = state.unloaded

    # Methods that only return attributes that are loaded; nothing more

    def __getitem__(self, key: str) -> Any:
        if key in self._unloaded:
            return self.EMPTY_VALUE
        else:
            return super().__getitem__(key)

    def get(self, key: Any, default: Any = None) -> Any:
        if key in self._unloaded:
            return self.EMPTY_VALUE
        else:
            return super().get(key, default)


class SAModel(BaseModel):
    """ Base for SqlAlchemy models """

    class Config(BaseConfig):
        # Enabling orm_mode makes Pydantic pick attributes of objects when necessary
        orm_mode = True

        # Custom GetterDict
        getter_dict: Type[GetterDict] = SAGetterDict

        # Forbid extra attributes
        extra = Extra.forbid


class SALoadedModel(SAModel):
    """ Base for SqlAlchemy models that will only return attributes that are already loaded """

    class Config(SAModel.Config):
        # GetterDict that won't trigger the loading of any attributes
        getter_dict = SALoadedGetterDict


# SqlAlchemyModel
SAModelT = TypeVar('SAModelT', bound=DeclarativeMeta)


# Model class
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
ForwardRefGeneratorT = Union[str, Literal[id], ForwardRefGeneratorFunction]


# Make all fields optional except the primary key
ALL_BUT_PRIMARY_KEY = object()


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
                 forwardref: ForwardRefGeneratorT,
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
                 ) -> Union[Type[ModelT], Type[SAModel], Type[BaseModel]]:
        """ Add a model to the group

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


def sa_model(Model: Type[SAModelT],
             Parent: Type[ModelT] = SAModel,
             *,
             module: str = None,
             types: AttributeType = AttributeType.COLUMN,
             make_optional: MakeOptionalFilterT = False,
             only_readable: bool = False,
             only_writable: bool = False,
             exclude: ExcludeFilterT = (),
             forwardref: Optional[ForwardRefGeneratorT] = None
             ) -> Union[Type[ModelT], Type[SAModel], Type[BaseModel]]:
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
            or a function(name, attribute) to select specific optional fields.
            Special case: `ALL_BUT_PRIMARY_KEY` will make all fields optional except for the primary key
        only_readable: only include fields that are readable. Useful for output models.
        only_writable: only include fields that are writable. Useful for input models.
        exclude: a list of fields/field names to ignore, or a filter(name, attribute) to exclude fields dynamically
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
    forwardref = _prepare_forwardref_function(forwardref)

    # make_optional
    make_optional = _prepare_make_optional_function(make_optional, Model)

    # Create the model
    pd_model = create_model(
        __model_name=generate_model_name(Model, forwardref),
        __module__=module,
        __base__=Parent,
        **sa_model_fields(Model, types=types,
                          exclude=exclude, make_optional=make_optional,
                          only_readable=only_readable,
                          only_writable=only_writable,
                          forwardref=forwardref
                          )
    )
    pd_model.__doc__ = Model.__doc__
    return pd_model


def sa_model_fields(Model: DeclarativeMeta, *,
                    types: AttributeType = AttributeType.COLUMN,
                    make_optional: MakeOptionalFilterFunction,
                    only_readable: bool = False,
                    only_writable: bool = False,
                    exclude: ExcludeFilterT = (),
                    can_omit_nullable: bool = True,
                    forwardref: Optional[ForwardRefGeneratorFunction],
                    ) -> Dict[str, Tuple[type, Field]]:
    """ Take an SqlAlchemy model and generate pydantic Field()s from it

    It will use sa_model_info() to extract attribute information from the SqlAlchemy model.
    Only fields selected by `types` & `exclude` will be considered.
    If SqlAlchemy model contains type annotations, they will override column types.

    Args:
        Model: the model to generate fields from
        types: attribute types to include. See AttributeType
        make_optional: a function(name, attribute) that selects fields to make Optional[]
        only_readable: only include fields that are readable
        only_writable: only include fields that are writable
        exclude: a list of fields/field names to ignore, or a filter(name, attribute) to exclude fields dynamically
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
            pydantic_field_type(name, info, model_annotations, make_optional(name, info.attribute), forwardref),
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


def generate_model_name(Model: DeclarativeMeta, forwardref: Optional[ForwardRefGeneratorFunction]) -> str:
    """ Generate a name for the model """
    if forwardref:
        return forwardref(Model)
    else:
        return Model.__name__


def pydantic_field_type(attr_name: str,
                        attr_info: AttributeInfo,
                        model_annotations: Dict[str, type],
                        make_optional: bool,
                        forwardref: Optional[ForwardRefGeneratorT],
                        ) -> type:
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

    # Get the type
    type_ = model_annotations.get(attr_name, attr_info.final_value_type)

    # make_optional?
    if make_optional:
        type_ = Optional[type_]

    # Done
    return type_


def _prepare_forwardref_function(forwardref: Optional[ForwardRefGeneratorT]) -> Optional[ForwardRefGeneratorFunction]:
    """ Given the `forwardref` argument, convert it into a guaranteed Optional[callable]

    If the argument is a function, leave it as it is.
    If the argument is a string, treat it like '{model}Input' pattern, and get a ForwardRef from it.
    Otherwise, do nothing: return as it is.
    """
    # If a string is given, it's a pattern
    if isinstance(forwardref, str):
        forwardref_str = forwardref
        assert '{model' in forwardref_str, 'The `forwardref` string must contain a reference to {model}'
        return lambda model: forwardref_str.format(model=model.__name__)
    # `None` is acceptable
    elif forwardref is None:
        return forwardref
    # Callable is ok
    elif isinstance(forwardref, Callable):
        return forwardref
    # Complain
    else:
        raise ValueError(forwardref)


def _prepare_make_optional_function(make_optional: MakeOptionalFilterT, Model: ModelT) -> MakeOptionalFilterFunction:
    """ Given the `make_optional` argument, convert it into a guaranteed callable """
    # True, False, None: as is
    if make_optional is None or make_optional is False:
        return lambda name, attr: False
    elif make_optional is True:
        return lambda name, attr: True
    # Special case: make all optional but the primary key
    elif make_optional is ALL_BUT_PRIMARY_KEY:
        primary_key_names = frozenset(c.key for c in inspect(Model).primary_key)
        return lambda name, attr: name not in primary_key_names
    # Callable is ok
    elif isinstance(make_optional, Callable):
        return make_optional
    # Iterable: a list of columns / column names
    elif isinstance(make_optional, Iterable):
        make_optional = _ColumnsOrColumnNames(make_optional)
        return lambda name, attr: name in make_optional or attr in make_optional

    # Complain
    else:
        raise ValueError(make_optional)
