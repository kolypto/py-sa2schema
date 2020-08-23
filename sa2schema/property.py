from functools import lru_cache
from typing import Set, Callable, Optional, TypeVar
from sqlalchemy.ext.declarative import DeclarativeMeta

import sa2schema


SameFunction = TypeVar('SameFunction')


def loads_attributes(*attribute_names: str) -> Callable:
    """ Mark a @property with the list of attributes that it uses.

    Loaders that support it will take the information into account and try to avoid numerous lazy-loads.
    For instance, sa2.pydantic by default will ignore propertiest that are not annotated with @loads_attributes

    Example:
        class User(Base):
            ...

            @property
            @loads_attributes('age')
            def age_in_100_years(self):
                return self.age + 100
    """
    def wrapper(fget: SameFunction) -> SameFunction:
        # TODO: implement some sort of "DEBUG MODE" that will detect when additional, unannounced, attributes are loaded
        setattr(fget, 'loads_atributes', set(attribute_names))
        return fget
    return wrapper


def get_property_loads_attribute_names(prop: property) -> Optional[Set[str]]:
    """ Get the list of attributes that a property requires """
    try:
        return prop.fget.loads_atributes
    except AttributeError:
        return None


@lru_cache(typed=True)
def get_all_safely_loadable_properties(Model: DeclarativeMeta):
    """ Get all properties with @loads_attributes

    Returns:
        { property-name => set(attribute-names) }
    """
    all_properties = sa2schema.sa_model_info(Model, types=sa2schema.AttributeType.PROPERTY_R |
                                                          sa2schema.AttributeType.HYBRID_PROPERTY_R)
    return {
        property_name: property_info.loads_attributes
        for property_name, property_info in all_properties.items()
        if property_info.loads_attributes
    }
