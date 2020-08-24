import pkg_resources
__version__ = pkg_resources.get_distribution('sa2schema').version


from .defs import AttributeType
from .annotations import SAAttributeType
from . import filter

from .sa_extract_info import sa_model_info, sa_attribute_info
from .sa_extract_info import sa_attribute_info
from .sa_extract_info import sa_model_primary_key_names, sa_model_primary_key_info
from .sa_extract_info import all_sqlalchemy_model_attributes, all_sqlalchemy_model_attribute_names

from .property import loads_attributes

# Shortcuts:
# import sa2schema as sa2
# sa2.pydantic.sa_model()
from .to import pydantic
