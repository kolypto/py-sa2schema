import pkg_resources
__version__ = pkg_resources.get_distribution('sa2schema').version

# import me:
# import sa2schema as sa2

# Types
from .annotations import SAAttributeType
from sa2schema.info.defs import AttributeType

# Model info
from sa2schema.info.sa_extract_info import sa_model_info
from sa2schema.info.sa_extract_info import sa_attribute_info, sa_model_attributes_by_type
from sa2schema.info.sa_extract_info import sa_model_primary_key_names, sa_model_primary_key_info
from sa2schema.info.sa_extract_info import all_sqlalchemy_model_attributes, all_sqlalchemy_model_attribute_names

# Filtering
from .info import filter

# Additional information
from sa2schema.info.property import loads_attributes, loads_attributes_readcode

# Conversion
from .pluck import sa_pluck, pluck_dict, Unloaded

# Schemas:
from .to import pydantic
