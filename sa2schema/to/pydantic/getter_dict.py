""" Implementations of GetterDict: a wrapper that makes an SqlAlchemy model look like a dict """

from typing import Iterator, Any, Set, Mapping

from pydantic.utils import GetterDict
from sqlalchemy.orm.base import instance_state
from sqlalchemy.orm.state import InstanceState

from sa2schema.property import get_all_safely_loadable_properties
from sa2schema.sa_extract_info import all_sqlalchemy_model_attribute_names
from sa2schema.util import loaded_attribute_names


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
    """ Adapter that extracts only the loaded data from SqlAlchemy models, leaving every other field None

    The advantage of this GetterDict is that it will never trigger loading of any SqlAlchemy
    attributes that aren't loaded.

    Be careful, though: if a field isn't loaded, this getter will return a None,
    which might not always make sense to your application.
    """
    __slots__ = ('_loaded', '_safe_properties', '_excluded')

    #: const: the value to return for unloaded attributes
    #: Note that the very same value will be used for collections as well.
    #: Special: `pydantic.main._missing` will make Pydantic return Field defaults instead.
    #: see: pydantic.validate_model()
    EMPTY_VALUE = None

    #: Cached set of loaded attributes.
    #: We cache it because it's not supposed to be modified while we're iterating the model
    _loaded: Set[str]

    #: List of all @property attributes that have @loads_attributes
    #: { property-name: list of attributes it loads }
    _safe_properties: Mapping[str, Set[str]]

    #: List of attribute that we have not included into the end result.
    #: This list will be removed from BaseModel.__fields_set__
    _excluded: Set[str]

    def __init__(self, obj: object):
        super().__init__(obj)

        # Make a list of attributes the loading of which would lead to an unwanted DB query
        state: InstanceState = instance_state(self._obj)
        self._loaded = loaded_attribute_names(state)
        self._safe_properties = get_all_safely_loadable_properties(type(obj))

        # Now, because we're going to ignore some of the unloaded attributes, we'll need to set BaseModel.__fields_set__.
        # However, we do not have any BaseModel here. Unfortunately.
        # Therefore, we have to collect those unloaded fields and stash them somewhere.
        # Where? Inside the intance itself: InstanceState.info is a perfect place
        # Then, SALoadedModel will pick it up and set `__fields_set__` for us
        self._excluded = state.info[SALoadedGetterDict] = set()

    @classmethod
    def get_names_excluded_from(cls, obj: object) -> Set[str]:
        """ Get the list of attribute names that SALoadedGetterDict has excluded

        See SALoadedGetterDict._excluded
        """
        return instance_state(obj).info[SALoadedGetterDict]

    # Methods that only return attributes that are loaded; nothing more

    def __getitem__(self, key: str) -> Any:
        # Loaded attribute.
        # Or a @property , with all its attributes loaded.
        # Go ahead.
        if key in self._loaded or (key in self._safe_properties and self._safe_properties[key] <= self._loaded):
            return super().__getitem__(key)
        # something unloaded. Do not touch; otherwise, we'll get numerous lazy loads
        else:
            self._excluded.add(key)
            return self.EMPTY_VALUE

    # same thing, but with a `default`

    def get(self, key: Any, default: Any = None) -> Any:
        if key in self._loaded or (key in self._safe_properties and self._safe_properties[key] <= self._loaded):
            return super().get(key, default)
        else:
            self._excluded.add(key)
            return self.EMPTY_VALUE
