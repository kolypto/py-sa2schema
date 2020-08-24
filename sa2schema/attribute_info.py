""" Dataclasses for information about an SqlAlchemy attribute, and methods to extract it

All this stuff is low-level; it's unlikely that you'll ever need is for anything other than reading.

If there every is a custom field that's unsupported by this library, do this:

1. Subclass AttributeInfo
2. Implement: extracts() to return AttributeType.APPLICATION_CUSTOM
3. Implement: matches() to react to your field
4. Implement: extract() to create a dataclass for your field
5. Enjoy. The library will pick your class up automatically: it automatically registers every available subclass.

If you're building a library, however, don't use APPLICATION_CUSTOM because it may clash with other libraries.
Subclass AttributeType and provide that a flag for your library. This might work... :D
"""

from __future__ import annotations

from contextlib import suppress
from copy import copy
from dataclasses import dataclass
from typing import Any, Optional, Union, Callable, Iterable, TypeVar, Type, List, Set, Dict
from typing import get_type_hints, ForwardRef, Tuple

from pydantic.utils import lenient_issubclass
from sqlalchemy import Column, ColumnDefault
from sqlalchemy.ext.associationproxy import AssociationProxyInstance
from sqlalchemy.ext.declarative import DeclarativeMeta
from sqlalchemy.ext.hybrid import hybrid_property, hybrid_method
from sqlalchemy.orm import CompositeProperty, RelationshipProperty, ColumnProperty
from sqlalchemy.orm.attributes import InstrumentedAttribute, QueryableAttribute
from sqlalchemy.orm.base import InspectionAttr, MANYTOMANY, MANYTOONE, ONETOMANY
from sqlalchemy.orm.dynamic import DynaLoader
from sqlalchemy.sql import ColumnElement, Selectable
from sqlalchemy.sql.elements import Label
from sqlalchemy.sql.type_api import TypeEngine
from sqlalchemy.util import symbol

from .annotations import SAAttributeType
from .compat import Literal, get_args, get_origin
from .defs import AttributeType
from .property import get_property_loads_attribute_names

# Value not provided (e.g. `default` value)
NOT_PROVIDED = symbol('NOT_PROVIDED')



# AttributeInfo type variable
Info_T = TypeVar('Info_T')


@dataclass
class AttributeInfo:
    """ Information about an SqlAlchemy attribute. Base class."""
    # To support new properties on SqlAlchemy models, just implement another class.
    # If the extracted type is unsatisfactory, it can be overridden with annotations.

    # Attribute type
    attribute_type: AttributeType

    # Attribute itself
    attribute: SAAttributeType

    # Is it nullable?
    nullable: bool

    # Access type
    readable: bool
    writable: bool

    # Type of the value from the column
    # For relationships, it's wrapped with the container types
    value_type: type

    # Default value, or NOT_PROVIDED
    default: Union[Optional[Any], Literal[NOT_PROVIDED]]  # noqa

    # Default value factory, or None
    # Guaranteed to be a simple type, not some complicated SqlAlchemy wrapperN
    default_factory: Optional[callable]

    # Documentation
    doc: Optional[str]

    @property
    def final_value_type(self) -> type:
        if self.nullable and self.value_type is not Any:
            return Optional[self.value_type]
        else:
            return self.value_type

    # All implementations

    @classmethod
    def all_implementations(cls) -> Iterable[Type[AttributeInfo]]:
        return get_deep_subclasses(cls)

    # Methods for data extraction, implementation-specific

    @staticmethod
    def extracts() -> AttributeType:
        """ Declare which attribute types this class is able to extract """
        raise NotImplementedError

    @classmethod
    def matches(cls, attr: InspectionAttr, types: AttributeType) -> bool:
        """ Does this class match a particular attribute? """
        raise NotImplementedError

    @classmethod
    def extract(cls: Type[Info_T], attr: InspectionAttr) -> Info_T:
        raise NotImplementedError


@dataclass
class ColumnInfo(AttributeInfo):
    """ Extract info: column

    Extracts:
    * value_type: from Column(...)
    * nullable: from Column(nullable=...)
    * readable: always, writable: always
    * default: from Column(default=...)
    * doc: from Column(doc=...)
    """
    @staticmethod
    def extracts() -> AttributeType:
        return AttributeType.COLUMN

    @classmethod
    def matches(cls, attr: InspectionAttr, types: AttributeType):
        return isinstance(attr, InstrumentedAttribute) and \
               isinstance(attr.property, ColumnProperty) and \
               isinstance(attr.expression, Column)  # not an expression

    @classmethod
    def extract(cls, attr: InstrumentedAttribute) -> ColumnInfo:
        column: Column = attr.expression

        # Extract the default value
        default = attr.default
        # SqlALchemy likes to wrap it into `ColumnDefault`
        if isinstance(default, ColumnDefault):
            default = default.arg
        # SqlAlchemy supports defaults that are: callable, SQL expressions
        # we do not support that, so it's ignored.
        if isinstance(default, (Callable, ColumnElement, Selectable)):
            default = NOT_PROVIDED
        # ignore `None` for non-nullable columns
        if default is None and not column.nullable:
            default = NOT_PROVIDED

        return cls(
            attribute_type=AttributeType.COLUMN,
            attribute=attr,
            nullable=column.nullable,
            readable=True,
            writable=True,
            value_type=get_type_from_sqlalchemy_type(attr.expression.type),
            default=default,
            default_factory=None,
            doc=attr.property.doc
        )


@dataclass
class PropertyInfo(AttributeInfo):
    """ Extract info: @property

    Extracts:
    * value_type: from the annotation of the return value
    * nullable: from `value_type`, if it's Optional[]
    * readable: fget() is set, writable: fset() is set
    * default: from setter's function argument's annotation (if any)
    * doc: from docstring
    """

    # The list of attribute names that this property loads when accessed.
    # Only available when @loads_attributes is used on it.
    loads_attributes: Optional[Set[str]] = None

    @staticmethod
    def extracts() -> AttributeType:
        return AttributeType.PROPERTY_R | \
               AttributeType.PROPERTY_W | \
               AttributeType.PROPERTY_RW

    @classmethod
    def matches(cls, attr: InspectionAttr, types: AttributeType):
        return isinstance(attr, property) and (
            ((types & AttributeType.PROPERTY_R) and attr.fget)
            or
            ((types & AttributeType.PROPERTY_W) and attr.fset)
        )

    @classmethod
    def extract(cls, attr: property) -> PropertyInfo:
        readable = bool(attr.fget)
        writable = bool(attr.fset)
        value_type = get_function_return_type(attr.fget)
        nullable = is_Optional_type(value_type)

        # note: when `nullable=True`, the type will be typing.Union[..., NoneType]
        if nullable:
            value_type = unwrap_Optional_type(value_type)

        # Try to get the default from a setter function's first argument
        try:
            default = attr.fset.__defaults__[0]  # noqa
        # no setter, or no default value, or no defaults at all
        except (AttributeError, IndexError, TypeError):
            default = NOT_PROVIDED

        # attribute_type
        if readable and writable:
            attribute_type = AttributeType.PROPERTY_RW
        elif readable:
            attribute_type = AttributeType.PROPERTY_R
        elif writable:
            attribute_type = AttributeType.PROPERTY_W
        else:
            raise AssertionError('what sort of weird property is that??!')

        return cls(
            attribute_type=attribute_type,
            attribute=attr,
            nullable=nullable,
            readable=readable,
            writable=writable,
            loads_attributes=get_property_loads_attribute_names(attr),
            value_type=value_type,
            default=default,
            default_factory=None,
            doc=attr.__doc__,
        )


@dataclass
class HybridPropertyInfo(PropertyInfo):
    """ Extract info: @hybrid_property

    Same as @property
    """
    @staticmethod
    def extracts() -> AttributeType:
        return AttributeType.HYBRID_PROPERTY_R | \
               AttributeType.HYBRID_PROPERTY_W | \
               AttributeType.HYBRID_PROPERTY_RW

    @classmethod
    def matches(cls, attr: InspectionAttr, types: AttributeType):
        return isinstance(attr, hybrid_property) and (
            ((types & AttributeType.HYBRID_PROPERTY_R) and attr.fget)
            or
            ((types & AttributeType.HYBRID_PROPERTY_W) and attr.fset)
        )

    @classmethod
    def extract(cls, attr: hybrid_property) -> HybridPropertyInfo:
        info = super().extract(attr)  # same thing, basically
        info.attribute_type = {
            # Translate attribute_type
            AttributeType.PROPERTY_R: AttributeType.HYBRID_PROPERTY_R,
            AttributeType.PROPERTY_W: AttributeType.HYBRID_PROPERTY_W,
            AttributeType.PROPERTY_RW: AttributeType.HYBRID_PROPERTY_RW,
        }[info.attribute_type]
        return info


@dataclass
class HybridMethodInfo(AttributeInfo):
    """ Extract info: @hybrid_method()

    * value_type: method annotation
    * nullable: method annotation
    * readable: yes, writable: no
    * default: NOT_PROVIDED
    * doc: from docstring
    """
    @staticmethod
    def extracts() -> AttributeType:
        return AttributeType.HYBRID_METHOD

    @classmethod
    def matches(cls, attr: InspectionAttr, types: AttributeType):
        return isinstance(attr, hybrid_method)

    @classmethod
    def extract(cls, attr: hybrid_method) -> HybridMethodInfo:
        value_type = get_function_return_type(attr.func)
        nullable = is_Optional_type(value_type)

        return cls(
            attribute_type=AttributeType.HYBRID_METHOD,
            attribute=attr,
            nullable=nullable,
            readable=True,
            writable=False,  # a method is not a writable entity... or is it?
            value_type=value_type,
            default=NOT_PROVIDED,
            default_factory=None,
            doc=attr.func.__doc__,
        )


@dataclass
class ColumnExpressionInfo(AttributeInfo):
    """ Extract info: column_property() expression

    * value_type: from column_property() expression
    * nullable: True (you never know)
    * readable: yes, writable: no
    * default: NOT_PROVIDED
    * doc: from column_property()
    """
    @staticmethod
    def extracts() -> AttributeType:
        return AttributeType.EXPRESSION

    @classmethod
    def matches(cls, attr: InspectionAttr, types: AttributeType):
        return isinstance(attr, InstrumentedAttribute) and \
               isinstance(attr.expression, Label)

    @classmethod
    def extract(cls, attr: InstrumentedAttribute) -> ColumnExpressionInfo:
        return cls(
            attribute_type=AttributeType.EXPRESSION,
            attribute=attr,
            nullable=True,  # everything's possible; let's be lax
            readable=True,
            writable=False,
            value_type=get_type_from_sqlalchemy_type(attr.expression.type),
            default=NOT_PROVIDED,  # not possible
            default_factory=None,
            doc=attr.property.doc
        )


@dataclass
class CompositeInfo(AttributeInfo):
    """ Extract info: composite()

    * value_type: method annotation
    * nullable: method annotation
    * readable: yes, writable: yes
    * default: NOT_PROVIDED
    * doc: from docstring
    """
    @staticmethod
    def extracts() -> AttributeType:
        return AttributeType.COMPOSITE

    @classmethod
    def matches(cls, attr: InspectionAttr, types: AttributeType):
        return isinstance(attr, QueryableAttribute) and \
               isinstance(attr.property, CompositeProperty)

    @classmethod
    def extract(cls, attr: QueryableAttribute) -> CompositeInfo:
        prop: CompositeProperty = attr.property
        return cls(
            attribute_type=AttributeType.COMPOSITE,
            attribute=attr,
            nullable=False,  # composite does not support nulls
            readable=True,
            writable=True,
            value_type=prop.composite_class,
            default=NOT_PROVIDED,  # not possible
            default_factory=None,
            doc=attr.property.doc
        )

    def replace_value_type(self, value_type: Union[type, ForwardRef]) -> CompositeInfo:
        """ Get a copy with `value_type` replaced.

        see: RelationshipInfo.replace_model() for more information
        """
        info = copy(self)
        info.value_type = value_type
        return info


@dataclass
class RelationshipInfo(AttributeInfo):
    """ Extract info: relationship()

    * value_type: target model, or List[model], Set[model]
    * nullable: yes, when not `uselist`
    * readable: yes, writable: unless `viewonly`
    * default: NOT_PROVIDED
    * doc: relationship(doc=)
    """
    # The model the relationship refers to
    target_model: DeclarativeMeta

    # Relationship to multiple values
    uselist: bool

    # Collection class: may be a type, or some sort of callable
    collection_class: Optional[Union[type, Callable]]

    @property
    def is_one2many(self):
        """ Is the relationship a One-TO-Many? """
        return self.attribute.property.direction is ONETOMANY

    @property
    def is_many2one(self):
        """ Is the relationship a Many-to-One? """
        return self.attribute.property.direction is MANYTOONE

    @property
    def is_many2many(self):
        """ Is the relationship a Many-to-Many? """
        return self.attribute.property.direction is MANYTOMANY

    # Core features

    @property
    def final_value_type(self) -> type:
        # For `uselist` values, wrap it into a collection class
        if self.uselist:
            # It's already wrapped with a collection class
            return self.value_type
        # For non-`uselist` values, wrap it into Optional[] class, if applicable
        else:
            return super().final_value_type

    @staticmethod
    def extracts() -> AttributeType:
        return AttributeType.RELATIONSHIP

    @classmethod
    def matches(cls, attr: InspectionAttr, types: AttributeType):
        return isinstance(attr, InstrumentedAttribute) and \
               isinstance(attr.property, RelationshipProperty) and \
               not isinstance(attr.property.strategy, DynaLoader)

    @classmethod
    def extract(cls: Type[Class_T], attr: InstrumentedAttribute) -> Class_T:
        prop: RelationshipProperty = attr.property

        # Value type and listings
        target_model = value_type = prop.mapper.class_
        nullable = not prop.uselist
        collection_class = prop.collection_class or (list if prop.uselist else None)

        # Wrap into the collection class
        default_factory, value_type = cls._wrap_value_type_with_collection_class(prop, collection_class, value_type)

        return cls(
            attribute_type=AttributeType.RELATIONSHIP,
            attribute=attr,
            nullable=nullable,
            readable=True,
            writable=not prop.viewonly,
            value_type=value_type,
            target_model=target_model,
            uselist=prop.uselist,
            collection_class=collection_class,
            default=None if nullable else NOT_PROVIDED,
            default_factory=default_factory,
            doc=prop.doc,
        )

    @staticmethod
    def _wrap_value_type_with_collection_class(prop, collection_class, value_type):
        if prop.uselist:
            return wrap_type_into_collection_class(value_type, collection_class)
        else:
            return None, value_type

    def replace_model(self, Model: Union[DeclarativeMeta, ForwardRef, type]) -> RelationshipInfo:
        """ Replace the model type with another type.

        This is needed by the SqlAlchemy-to-Pydantic converter: you can't just keep referring to SqlAlchemy models
        in a Pydantic context; you'll need to replace the target relationship model with a Pydantic model.

        Complicated?
        Ok, look. Let's convert a `User` model from SqlAlchemy to Pydantic using some low-level functions:

            class User(Base):
                ...
                articles = relationship(Article)

        if this model is converted straight to Pydantic using info from RelationshipInfo,
        it will look like this:

            class UserSchema(BaseModel):
                article: List[Article]  # not a Pydantic model, but an SqlAlchemy model

        Pydantic won't be able to work with this `Article`; it's not a model it can validate.
        Therefore, before using RelationshipInfo, we have to replace `Article` with
        something that makes sense to Pydantic: namely, a Pydantic-generated model.

        Returns:
            a copy, with the model replaced
        """
        new = copy(self)

        # self.target_model
        new.target_model = Model

        # self.value_type
        new.value_type = Model

        # re-do something that extract() has already done
        _, new.value_type = new._wrap_value_type_with_collection_class(new.attribute.property, new.collection_class, new.value_type)

        # Done
        return new


@dataclass
class DynamicLoaderInfo(RelationshipInfo):
    """ Extract info: dynamic_loader() """
    @staticmethod
    def extracts() -> AttributeType:
        return AttributeType.DYNAMIC_LOADER

    @classmethod
    def matches(cls, attr: InspectionAttr, types: AttributeType):
        return isinstance(attr, InstrumentedAttribute) and \
               isinstance(attr.property, RelationshipProperty) and \
               isinstance(attr.property.strategy, DynaLoader)

    @classmethod
    def extract(cls: Type[Class_T], attr: InstrumentedAttribute) -> Class_T:
        info = super().extract(attr)
        info.attribute_type = AttributeType.DYNAMIC_LOADER
        return info


@dataclass
class AssociationProxyInfo(AttributeInfo):
    """ Extract info: association_proxy()

    * value_type: target model, or List[model], Set[model]
    * nullable: yes, when not `uselist`
    * readable: yes, writable: no
    * default: NOT_PROVIDED
    * doc: none
    """
    # The model the relationship refers to
    target_model: DeclarativeMeta

    # Collection class: may be a type, or some sort of callable
    collection_class: Optional[Union[type, Callable]]

    @staticmethod
    def extracts() -> AttributeType:
        return AttributeType.ASSOCIATION_PROXY

    @classmethod
    def matches(cls, attr: InspectionAttr, types: AttributeType):
        return isinstance(attr, AssociationProxyInstance)

    @classmethod
    def extract(cls, attr: AssociationProxyInstance) -> AssociationProxyInfo:
        collection_class = attr.collection_class or dict
        value_type = get_type_from_sqlalchemy_type(attr.remote_attr.type)

        # Wrap with collection class
        target_model = attr.target_class
        default_factory, value_type = cls._wrap_value_type_with_collection_class(target_model, value_type, collection_class)

        return cls(
            attribute_type=AttributeType.ASSOCIATION_PROXY,
            attribute=attr,
            nullable=attr.scalar,
            readable=True,
            writable=False,
            value_type=value_type,
            target_model=attr.target_class,
            collection_class=collection_class,
            default=NOT_PROVIDED,
            default_factory=default_factory,
            doc=None,
        )

    @staticmethod
    def _wrap_value_type_with_collection_class(target_model, value_type, collection_class):
        if collection_class is None or issubclass(collection_class, dict):
            return dict, Dict[value_type, target_model]
        else:
            return wrap_type_into_collection_class(value_type, collection_class)

    def replace_model(self, Model: Union[DeclarativeMeta, ForwardRef, type]) -> AssociationProxyInfo:
        """ Replace the model type with another type.
        
        See: RelationshipInfo.replace_model()
        """
        info = copy(self)
        value_type = get_type_from_sqlalchemy_type(info.attribute.remote_attr.type)
        info.target_model = Model
        _, info.value_type = self._wrap_value_type_with_collection_class(info.target_model, value_type, info.collection_class)
        return info


def is_Optional_type(t: type):
    """ Check if the given type is Optional[] """
    # https://stackoverflow.com/questions/56832881/check-if-a-field-is-typing-optional
    # An Optional[] type is actually an alias for Union[..., NoneType]
    # This type has t.__origin__=typing.Union and t.__args__=[..., NoneType]
    # get_origin() won't fail: it returns None for non-typing types (Python 3.8+)
    return t is Any or (
        get_origin(t) is Union and
        type(None) in get_args(t)
    )


def unwrap_Optional_type(t: type) -> type:
    """ Given an Optional[...], return the wrapped type """
    if get_origin(t) is Union:
        # Optional[...] = Union[..., NoneType]
        args = tuple(a
                     for a in get_args(t)
                     if a is not type(None))
        if len(args) == 1:
            return args[0]
        else:
            return Union[args]
    return t


def get_function_return_type(function: callable) -> Union[type, Any]:
    """ Get the return value's type of a function """
    return get_type_hints(function).get('return', Any)


def get_type_from_sqlalchemy_type(sa_type: TypeEngine) -> type:
    """ Get a python type from an SqlAlchemy type """
    try:
        # may throw errors
        return sa_type.python_type
    except NotImplementedError:
        return Any


def wrap_type_into_collection_class(value_type: type, collection_class: Union[type, callable]) -> Tuple[Optional[callable], Type]:
    """ Wrap a type into a collection

    Returns:
        a tuple:
        [0] default_factory: the factory of a default value
        [1] type: the type for the value
    """
    if lenient_issubclass(collection_class, (list, List)):
        return list, List[value_type]
    elif lenient_issubclass(collection_class, (set, Set)):
        return set, Set[value_type]
    elif lenient_issubclass(collection_class, (dict, Dict)):
        return dict, Dict[Any, value_type]
    else:
        # Try it as a callable. Retreat in case of any error
        with suppress(Exception):
            # phew! it went fine!
            collection_class_type = type(collection_class())
            return wrap_type_into_collection_class(value_type, collection_class_type)

        # Nothing worked.
        # No idea what type this might be. Something iterable.
        # `collection_class` can be any callable producing miracles
        return None, Union[List[value_type], Dict[Any, value_type]]


Class_T = TypeVar('Class_T')


def get_deep_subclasses(cls: Type[Class_T]) -> Iterable[Type[Class_T]]:
    """ Get all subclasses of the given class """
    for subclass in cls.__subclasses__():
        yield from get_deep_subclasses(subclass)
        yield subclass
