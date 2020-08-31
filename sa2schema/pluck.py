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
from typing import Mapping, Union

from sqlalchemy.orm import RelationshipProperty
from sqlalchemy.orm.base import instance_state
from sqlalchemy.orm.state import InstanceState

from .annotations import SAInstanceT

# The dict used for plucking
PluckMap = Mapping[str, Union[int, 'PluckMap']]


def sa_pluck(instance: SAInstanceT, map: PluckMap) -> dict:
    """ Recursively pluck an SqlAlchemy instance according to `map` into a dict

    Someone else has to validate the `map` dict and make sure that:
    * Assumption #1: `map` contains only valid attribute names. If not, expect AttributeError
    * Assumption #2 every relationship in `map` is a nested dict. If not, expect KeyError
    * Assumption #3 all attributes specified in `map` are loaded. If not, expect the N+1 problem

    Benchmark: 1M plucks in 7.8 seconds; down to 5.9 seconds when compiled with Cython

    Args:
        map: plucking map: {attribute: 1, relatiopnship: {key: 1, ...})
            Use `1` to include an attribute, dict() to include a relationship, `0` to exclude something

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
    state: InstanceState = instance_state(instance)
    relationships: Mapping[str, RelationshipProperty] = state.mapper.relationships

    # Pluck according to `map`
    ret = {}
    # For every key in `map`
    for key, include in map.items():
        # Unless the value is excluded (0, False), include it
        # Even empty dict()s count.
        if include != 0:
            # Get the value anyway
            value = getattr(instance, key)

            # Relationship
            if key in relationships:
                # Scalar relationship
                if not relationships[key].uselist:
                    ret[key] = sa_pluck(value, include)
                # Iterable relationship: list, set
                else:
                    ret[key] = [sa_pluck(item, include) for item in value]
            # JSON
            elif isinstance(value, dict) and isinstance(include, dict):
                ret[key] = pluck_dict(value, include)
            # Not a relationship
            else:
                ret[key] = value
    return ret


def pluck_dict(value: dict, map: PluckMap) -> dict:
    """ Pluck a dict

    Works in the same fashion as sa_pluck(), but plucks dictionaries.
    Supports recursion.
    Forgives missing keys.
    """
    return {
        key: pluck_dict(value[key], include) if isinstance(include, dict) and isinstance(value[key], dict) else value[key]
        for key, include in map.items()
        if include != 0 and key in value
    }
