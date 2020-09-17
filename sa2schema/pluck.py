""" Tools to help plucking SqlAlchemy instances

Plucking is normally done by Pydantic.BaseModel.from_orm(), but it needs some help.
Without our assistance, it would get every attribute it can.
This may include @property attributes that will in turn trigger the loading of other nested attributes.

To help with this, "plucking map" dictionaries are used, which look like this:

    {'id': 1, 'name': 1, 'property': 1, 'relationship': { 'attribute': 1 }}

Those dictionaries explicitly specify which attributes to load:

* `1` to load, `0` to skip
* nested dictionary to specify attributes for a relationship
* use `1` for a relationship to pluck loaded attributes only
"""
import warnings
import enum
from functools import lru_cache
from typing import Mapping, Union, Any, Callable, FrozenSet

from sqlalchemy.ext.declarative.api import DeclarativeMeta
from sqlalchemy.orm import Mapper
from sqlalchemy.orm.base import instance_dict, class_mapper

from .annotations import SAInstanceT
from .info import sa_model_info, AttributeType

# The dict used for plucking
PluckMap = Mapping[str, Union[int, 'PluckMap']]


@enum.unique
class Unloaded(enum.Enum):
    """ What to do if an attribute is not loaded, but requested to be plucked? """
    # Raise an AttributeError.
    # Ensures that you have preloaded everything.
    # Recommended for development.
    RAISE = enum.auto()

    # Return `None`.
    # This is the default SqlAlchemy behavior.
    NONE = enum.auto()

    # Lazy-load the attribute using getattr().
    # Only works if getattr() actually helps: e.g. with Declarative.
    # Can be very slow if something's missing.
    # Recommended for production.
    LAZY = enum.auto()

    # Lazy-load with a warning
    # Recommended for soft N+1 problem investigation
    LAZYWARN = enum.auto()

    # Skip unloaded fields (as if they have not been requested)
    # Recommended in cases where the UI should notice the difference
    SKIP = enum.auto()


def pluck_relationship(key: str, uselist: bool, value: Any, map: PluckMap, unloaded: Unloaded, context=None) -> Any:
    if not uselist:
        return sa_pluck(value, map, unloaded, relhandler=pluck_relationship, context=context)
    else:
        return [sa_pluck(item, map, unloaded, relhandler=pluck_relationship, context=context) for item in value]


def sa_pluck(instance: SAInstanceT, map: PluckMap, unloaded: Unloaded = Unloaded.RAISE, *,
             relhandler: Callable = pluck_relationship, context=None) -> dict:
    """ Recursively pluck an SqlAlchemy instance according to `map` into a dict

    Someone else has to validate the `map` dict and make sure that:
    * Assumption #1: `map` contains only valid attribute names. If not, expect AttributeError
    * Assumption #2 every relationship in `map` is a nested dict. If not, expect KeyError
    * Assumption #3 all attributes specified in `map` are loaded. If not, expect the N+1 problem

    Benchmark: 1M plucks in 7.8 seconds; down to 5.9 seconds when compiled with Cython

    Args:
        map: plucking map: {attribute: 1, relatiopnship: {key: 1, ...})
            Use `1` to include an attribute, dict() to include a relationship, `0` to exclude something
        unloaded: what to do if an attribute is not loaded

    Example:
        from sqlalchemy.orm import joinedload

        sa_pluck(
            ssn.query(User)
                .options(joinedload(User.articles))
                .first(),
            {'id': 1, 'login': 1,
             'articles': {'id': 1, 'title': 1}}
        )
    """
    Model = type(instance)
    rel_uses_list = uselist_relationships(Model)
    descriptors = descriptor_attributes(Model)
    dict_ = instance_dict(instance)

    # Pluck according to `map`
    ret = {}
    # For every key in `map`
    for key, include in map.items():
        # Skip excluded elements: (0, False).
        # Note: empty dicts are still included
        if include == 0:
            continue

        # Get the value
        if key in dict_:
            value = dict_[key]
        elif key in descriptors:
            value = getattr(instance, key)
        elif unloaded == Unloaded.NONE:
            value = None
        elif unloaded == Unloaded.LAZY:
            value = getattr(instance, key)
        elif unloaded == Unloaded.LAZYWARN:
            warnings.warn(f'Lazy loading {key!r} from {instance}')
            value = getattr(instance, key)
        elif unloaded == Unloaded.SKIP:
            continue
        elif unloaded == Unloaded.RAISE:
            raise AttributeError(key)
        else:
            raise IMPOSSIBLE

        # Relationship
        if key in rel_uses_list:
            uselist = rel_uses_list[key]
            # When a relationship has no loaded value
            if value is None:
                ret[key] = [] if uselist else None
            elif not include and uselist:
                ret[key] = []
            # Loaded relationship
            else:
                ret[key] = relhandler(key, uselist, value, include, unloaded, context)
        # JSON
        elif isinstance(value, dict) and isinstance(include, dict):
            ret[key] = pluck_dict(value, include)
        # Not a relationship
        else:
            ret[key] = value
    return ret


@lru_cache()
def uselist_relationships(Model: Union[type, DeclarativeMeta]) -> Mapping[str, bool]:
    """ Inspect a model and return a map of {relationship name => uselist} """
    mapper: Mapper = class_mapper(Model)
    return {
        rel.key: rel.uselist
        for rel in mapper.relationships
    }


@lru_cache()
def descriptor_attributes(Model: Union[type, DeclarativeMeta]) -> FrozenSet[str]:
    """ Names of descriptor attributes like @property

    These properties can only be plucked using getattr()
    """
    return frozenset(sa_model_info(Model, types=AttributeType.ALL_DESCRIPTORS))


def pluck_dict(value: dict, map: PluckMap) -> dict:
    """ Pluck a dict

    Works in the same fashion as sa_pluck(), but plucks dictionaries.
    Supports recursion.
    Forgives missing keys.
    """
    return {
        key: pluck_dict(value[key], include)
             if isinstance(include, dict) and isinstance(value[key], dict) else
             value[key]
        for key, include in map.items()
        if include != 0 and key in value
    }


IMPOSSIBLE = AssertionError
