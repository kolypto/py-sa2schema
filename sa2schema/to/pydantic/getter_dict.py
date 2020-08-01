""" Implementatins of GetterDict: a wrapper that makes an SqlAlchemy model look like a dict """

from typing import Iterator, Any, Set

from pydantic.utils import GetterDict
from sqlalchemy.orm.base import instance_state
from sqlalchemy.orm.state import InstanceState

from sa2schema.sa_extract_info import all_sqlalchemy_model_attribute_names


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
