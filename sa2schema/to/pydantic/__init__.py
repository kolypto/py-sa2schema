""" SA-Pydantic bridge between SqlAlchemy and Pydantic """

# Convert SqlAlchemy models to Pydantic models
from .sa_model import sa_model

# Namespace for models that can relate to one another
from .models import Models

# Pydantic Schema Tools
from .schema_tools import derive_model

# Base models for Pydantic-SqlAlchemy models
from .base_model import SAModel, SALoadedModel

# (low-level) getter dicts that implement SA attribute access
from .getter_dict import SAGetterDict, SALoadedGetterDict


# Shortcuts
# Useful for doing this:
# from sa2schema.pydantic import Models, sa_model, AttributeType
from sa2schema import *  # noqa
