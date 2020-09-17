import dis
import inspect
from functools import lru_cache
from typing import Set, Callable, Optional, TypeVar, Generator

import sa2schema as sa2
from .defs import AttributeType

SameFunction = TypeVar('SameFunction')


def loads_attributes(*attribute_names: str, check: bool = True) -> Callable:
    """ Mark a @property with the list of attributes that it uses.

    Loaders that support it will take the information into account and try to avoid numerous lazy-loads.
    For instance, sa2.pydantic by default will ignore properties that are not annotated with @loads_attributes

    Example:
        class User(Base):
            ...

            @property
            @loads_attributes('age')
            def age_in_100_years(self):
                return self.age + 100

    Args:
        *attribute_names: The names of attributes that the property touches.
        check: Check arguments by reading the code? Disable if gives errors.
            This increases your start-up time, but only by about 0.01ms per property
    """
    def wrapper(fget: SameFunction) -> SameFunction:
        # Check by reading the code
        if check:
            code_uses = set(func_uses_attributes(fget))
            mismatched_attribute = code_uses.symmetric_difference(attribute_names)
            assert not mismatched_attribute, (
                f'Your @property uses different attributes from what it has described. '
                f'Mismatch: {mismatched_attribute}'
            )

        # Remember
        setattr(fget, '_loads_attributes', frozenset(attribute_names))
        return fget
    return wrapper


def loads_attributes_readcode(*extra_attribute_names: str):
    """ Mark a @property with @loads_attributes(), read those attributes' names from the code

    This decorator will extract all accessed attribute names from the code; you won't have to maintain the list.
    Wasted start-up time: about 0.01ms per property

    Args:
        *extra_attribute_names: Additional attribute names (e.g. from invisible nested functions)
    """
    def wrapper(fget: SameFunction) -> SameFunction:
        return loads_attributes(
            *func_uses_attributes(fget),
            *extra_attribute_names,
            check=False
        )(fget)
    return wrapper


def get_property_loads_attribute_names(prop: property) -> Optional[Set[str]]:
    """ Get the list of attributes that a property requires """
    try:
        return prop.fget._loads_attributes
    except AttributeError:
        return None


@lru_cache(typed=True)
def get_all_safely_loadable_properties(Model: type):
    """ Get all properties with @loads_attributes

    Returns:
        { property-name => set(attribute-names) }
    """
    all_properties = sa2.sa_model_info(Model, types=AttributeType.PROPERTY_R | AttributeType.HYBRID_PROPERTY_R)
    return {
        property_name: property_info.loads_attributes
        for property_name, property_info in all_properties.items()
        if property_info.loads_attributes
    }


def func_uses_attributes(func: Callable) -> Generator[str, None, None]:
    """ Find all patterns of `self.attribute` and return those attribute names

    Supports both methods (`self`), class methods (`cls`), and weirdos (any name for `self`)
    """
    first_arg_name = next(iter(inspect.signature(func).parameters))
    return code_uses_attributes(func, first_arg_name)


def code_uses_attributes(code, object_name: str = 'self') -> Generator[str, None, None]:
    """ Find all patterns of `object_name.attribute` and return those attribute names """
    # Look for the following patterns:
    #   Instruction(opname='LOAD_FAST', argval='self') followed by
    #   Instruction(opname='LOAD_ATTR', argval='<attr-name>')
    # or
    #   Instruction(opname='LOAD_FAST', argval='self') followed by
    #   Instruction(opname='STORE_ATTR', argval='<attr-name>')
    prev_instruction = None
    for instruction in dis.get_instructions(code):
        if (
            instruction.opname in ('LOAD_ATTR', 'STORE_ATTR') and
            prev_instruction.opname == 'LOAD_FAST' and
            prev_instruction.argval == object_name
            ):
            yield instruction.argval
        prev_instruction = instruction

