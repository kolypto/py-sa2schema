try:
    from . import pydantic  # noqa
except ModuleNotFoundError as e:
    # If pydantic is not installed, ignore the error
    if e.name == 'pydantic':
        pydantic = None  # make sure the attribute is available
    else:
        raise
