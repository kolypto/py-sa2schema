""" Extract structural attribute information from SqlAlchemy models """
from __future__ import annotations

from functools import lru_cache
from typing import Mapping, Dict, Sequence, Tuple, Type

from sqlalchemy.ext.associationproxy import AssociationProxy
from sqlalchemy.ext.declarative import DeclarativeMeta
from sqlalchemy.orm import class_mapper, Mapper

from . import filter
from .annotations import FilterT
from .attribute_info import AttributeInfo, SAAttributeType
from .defs import AttributeType


def sa_model_info(Model: DeclarativeMeta, *,
                  types: AttributeType,
                  exclude: FilterT = (),
                  ) -> Mapping[str, AttributeInfo]:
    """ Extract information on every attribute of an SqlAlchemy model

    Note: it's really cheap to use this function because all the underlying information is cached.

    Args:
        Model: the model to extract the info about
        types: AttributeType types to inspect
        exclude: the list of fields to ignore, or a filter(name) to exclude fields dynamically.
            See also: sa2schema.filters for useful presets
    Returns:
        dict: Attribute names mapped to attribute info objects
    """
    # Get the full model info
    model_info = _sa_model_info(Model, types)

    # Prepare the filter
    exclude = filter.prepare_filter_function(exclude, Model)

    # Filter it
    return {
        name: attr_info
        for name, attr_info in model_info.items()
        if not exclude(name)
    }


@lru_cache(typed=True)  # makes it really, really cheap to inspect models
def _sa_model_info(Model: DeclarativeMeta, types: AttributeType) -> Mapping[str, AttributeInfo]:
    """ Get the full information about the model

    This function gets a full, cachable, information about the model's `types` attributes, once.
    sa_model_info() can then filter it the way it likes, without polluting the cache.
    """
    # Get a list of all available InfoClasses
    info_classes = [
        InfoClass
        for InfoClass in AttributeInfo.all_implementations()
        if InfoClass.extracts() & types  # only enabled types
    ]

    # Apply InfoClasses' extraction to every attribute
    # If there is any weird attribute that is not supported, it is silently ignored.
    return {
        name: InfoClass.extract(attribute)
        for name, attribute in all_sqlalchemy_model_attributes(Model).items()
        for InfoClass in info_classes
        if InfoClass.matches(attribute, types)
    }


@lru_cache(typed=True)
def sa_model_attributes_by_type(Model: DeclarativeMeta) -> Mapping[Type[AttributeType], Mapping[str, AttributeInfo]]:
    """ Get model attributes neatly grouped into categories """
    # Prepare categories.
    # They have to be all present, even if this particular model does not have some.
    attr_by_category = {
        AttributeInfoClass: dict()
        for AttributeInfoClass in AttributeInfo.all_implementations()
    }

    # Categorize
    for attr_name, attr_info in _sa_model_info(Model, AttributeType.ALL).items():
        attr_by_category[type(attr_info)][attr_name] = attr_info

    # Done
    return attr_by_category


@lru_cache(typed=True)
def sa_model_primary_key_names(Model: DeclarativeMeta) -> Tuple[str]:
    """ Get the list of primary key attribute names """
    return tuple(c.key for c in class_mapper(Model).primary_key)


@lru_cache(typed=True)
def sa_model_primary_key_info(Model: DeclarativeMeta) -> Mapping[str, AttributeInfo]:
    """ Extract information about the primary key of an SqlAlchemy model """
    return {
        attribute_name: sa_attribute_info(Model, attribute_name)
        for attribute_name in sa_model_primary_key_names(Model)
    }


@lru_cache(typed=True)
def sa_attribute_info(Model: DeclarativeMeta, attribute_name: str) -> AttributeInfo:
    """ Extract info from an individual attribute """
    # Get the attribute
    # We use this __dict__ workaround to avoid triggering descriptor behaviors
    attribute = Model.__dict__[attribute_name]

    # Normalize it: get a more useful value
    if isinstance(attribute, AssociationProxy):
        attribute = getattr(Model, attribute_name)

    # Find a matcher
    for InfoClass in AttributeInfo.all_implementations():
        if InfoClass.matches(attribute, InfoClass.extracts()):
            return InfoClass.extract(attribute)

    # Not found
    raise AttributeType(f'Attribute {attribute_name!r} has a type that is not currently supported')


@lru_cache(typed=True)
def all_sqlalchemy_model_attributes(Model: DeclarativeMeta) -> Dict[str, SAAttributeType]:
    """ Get all attributes of an SqlAlchemy model (ORM + @property) """
    mapper: Mapper = class_mapper(Model)
    return {
        name: (
            # In some cases, we need to call an actual getattr() to make sure
            # the property descriptor invokes its __get__()
            # For instance: vars() gives us a useless AssociationProxy object,
            # whilst getattr() gives an AssociationProxyInstance, which, unlike its parent, knows its class.
            getattr(Model, name)
            if isinstance(prop, AssociationProxy) else
            prop
        )
        # Iterate vars() because then @property attributes will be included.
        # all_orm_descriptors doesn't have it.
        for name, prop in list(vars(Model).items())  # list() because it gets modified by descriptors as we iterate
        if name in mapper.all_orm_descriptors
           or isinstance(prop, property)}


@lru_cache(typed=True)
def all_sqlalchemy_model_attribute_names(Model: DeclarativeMeta) -> Sequence[str]:
    """ Get all attribute names of an SqlAlchemy model (ORM + @property) """
    mapper: Mapper = class_mapper(Model)
    return tuple(
        name
        for name, prop in list(vars(Model).items())  # list() because it gets modified by descriptors as we iterate
        if name in mapper.all_orm_descriptors
           or isinstance(prop, property)
    )
