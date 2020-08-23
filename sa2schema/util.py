from typing import Set
from sqlalchemy.orm.state import InstanceState


def loaded_attribute_names(state: InstanceState) -> Set[str]:
    """ Get the set of loaded attribute names """
    # This is the opposite of InstanceState.unloaded which is supposed to perform better
    # See: InstanceState.unloaded
    return set(state.dict) | set(state.committed_state)
