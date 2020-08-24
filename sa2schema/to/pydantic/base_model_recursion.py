""" Solutions to a recursion in BaseModel

When working with SqlAlchemy relationships that have a backref, which are many, SqlAlchemy establishes
a bi-directional link between the two. Such links lead to infinine recursion in two places:

1. In from_orm(), because Pydantic applies recursive parsing, and fails.
2. In dict(), if models reference one another

This module contains solutions to this issue.
"""

from contextlib import contextmanager
from typing import Optional, Hashable

from sqlalchemy.orm.base import instance_state
from sqlalchemy.orm.state import InstanceState

from .annotations import PydanticModelT, SAModelT


class NoneRecursiveParserMixin:
    """ Recursive solution with from_orm() that replaces recursive models with Nones.

    Note that some models' schemas might not be ready to receive those values; be
    """

    @classmethod
    def from_orm(cls: PydanticModelT, obj: SAModelT) -> Optional[PydanticModelT]:
        # Prevent recursive parsing. This is important for every relationship with a backref
        # because SqlAlchemy will typically establish a bi-directional reference, which will read to RecursionError.
        # Our approach is to replace them with None
        with prevent_model_recursion(obj, marker_key=('sa2.pydantic', 'from_orm()', cls)) as maybe_object:
            # In case of recursion, return `None`
            if maybe_object is None:
                return None
            # Otherwise, actually parse the model
            else:
                return super().from_orm(maybe_object)



@contextmanager
def prevent_model_recursion(obj: SAModelT, marker_key: Hashable) -> Optional[SAModelT]:
    """ Mark an instance as "being processed at the moment" and return it. In case of recursion, return None """
    # Prepare a place to mark the instance as "being processed"
    state: InstanceState = instance_state(obj)
    marker_key = marker_key

    # Is already being parsed? (recursion)
    if marker_key in state.info:
        yield None
        return

    # Mark the instance as "being processed at the moment"
    state.info[marker_key] = True

    # Parse it
    try:
        yield obj
    finally:
        # Unmark it
        del state.info[marker_key]
