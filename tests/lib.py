from sqlalchemy.orm.attributes import set_committed_value
from sqlalchemy.orm.base import instance_state
from sqlalchemy.orm.state import InstanceState


def sa_set_committed_state(obj: object, **committed_values):
    """ Put values into an SqlAlchemy instance as if they were committed to the DB """
    # Give it some DB identity so that SA thinks it can load something
    state: InstanceState = instance_state(obj)
    state.key = object()

    # Set every attribute in such a way that SA thinkg that's the way it looks in the DB
    for k, v in committed_values.items():
        set_committed_value(obj, k, v)

    return obj
