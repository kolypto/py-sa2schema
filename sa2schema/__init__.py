import pkg_resources
__version__ = pkg_resources.get_distribution('sa2schema').version


from .defs import AttributeType
from .attribute_info import SAAttributeType

from .sa_extract_info import sa_model_info, sa_attribute_info

# Nice shortcuts for you
# Use like this:
#   from sa2schema import sa2
#   sa2.pydantic.sa_model()
from . import to as sa_to
from . import to as sa2
