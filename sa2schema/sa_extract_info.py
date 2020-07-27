""" Extract structural attribute information from SqlAlchemy models """
from __future__ import annotations

from functools import lru_cache
from typing import Union, Callable, Mapping, Dict, Iterable

from sqlalchemy.ext.associationproxy import AssociationProxy
from sqlalchemy.ext.declarative import DeclarativeMeta
from sqlalchemy.orm import class_mapper, Mapper

from .attribute_info import AttributeInfo, SAAttributeType
from .defs import AttributeType


# A filter function that decides whether to exclude a certain field.
# function(field-name, attribute-object) -> bool
# return `True` to exclude a field, `False` to include it.
ExcludeFilterFunction = Callable[[str, SAAttributeType], bool]


# Exclude filter: a function, or a set of field names
ExcludeFilterT = Union[ExcludeFilterFunction, Iterable[str]]


@lru_cache(typed=True)  # makes it really, really cheap to inspect models
def sa_model_info(Model: DeclarativeMeta, *,
                  types: AttributeType,
                  exclude: ExcludeFilterT = (),
                  ) -> Mapping[str, AttributeInfo]:
    """ Extract information on every attribute of an SqlAlchemy model

    Args:
        Model: the model to extract the info about
        types: AttributeType types to inspect
        exclude: the list of fields to ignore, or a filter(name, attribute) to exclude fields dynamically
    Returns:
        dict: Attribute names mapped to attribute info objects
    """
    # Get a list of all available InfoClasses
    info_classes = [
        InfoClass
        for InfoClass in AttributeInfo.all_implementations()
        if InfoClass.extracts() & types  # only enabled types
    ]

    # Filter fields callable
    if isinstance(exclude, Callable):
        filter = exclude
    else:
        exclude = set(exclude)
        filter = lambda name, attr: name in exclude

    # Apply InfoClasses' extraction to every attribute
    # If there is any weird attribute that is not supported, it is silently ignored.
    return {
        name: InfoClass.extract(attribute)
        for name, attribute in all_sqlalchemy_model_attributes(Model).items()
        for InfoClass in info_classes
        if not filter(name, attribute) and InfoClass.matches(attribute, types)
    }


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
