from typing import Set, Type, TypeVar, Iterable

from sqlalchemy.orm.base import manager_of_class
from sqlalchemy.orm.state import InstanceState


def loaded_attribute_names(state: InstanceState) -> Set[str]:
    """ Get the set of loaded attribute names """
    # This is the opposite of InstanceState.unloaded which is supposed to perform better
    # See: InstanceState.unloaded
    return set(state.dict) | set(state.committed_state)


def is_sa_mapped_class(class_: type) -> bool:
    """ Tell whether the object is an class mapped by SqlAlchemy, declarative or not """
    return manager_of_class(class_) is not None


Class_T = TypeVar('Class_T')


def get_deep_subclasses(cls: Type[Class_T]) -> Iterable[Type[Class_T]]:
    """ Get all subclasses of the given class """
    for subclass in cls.__subclasses__():
        yield from get_deep_subclasses(subclass)
        yield subclass
