""" SA-Pydantic bridge between SqlAlchemy and Pydantic """

# Convert SqlAlchemy models to Pydantic models
from .sa_model import sa_model

# Convert SqlAlchemy models that can relate to one another
from .sa_models import sa_models

# Pydantic Schema Tools
from .schema_tools import derive_model, merge_models

# Base models for Pydantic-SqlAlchemy models
from .base_model import SAModel, SALoadedModel

# (low-level) getter dicts that implement SA attribute access
from .getter_dict import SAGetterDict, SALoadedGetterDict


# Shortcuts
# Useful for doing this:
# from sa2schema.pydantic import sa_models, sa_model, AttributeType
from sa2schema import *  # noqa
