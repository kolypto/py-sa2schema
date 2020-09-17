from __future__ import annotations

from enum import Flag, auto


class AttributeType(Flag):
    """ SqlAlchemy attribute type flags

    This is a set of flags that can be combined to define which fields to use
    """
    NONE = 0  # empty value

    # Regular columns
    COLUMN = auto()

    # @property: readable, writable
    PROPERTY_R = auto()  # readable properties
    PROPERTY_W = auto()  # writable properties
    PROPERTY_RW = PROPERTY_R | PROPERTY_W  # readable properties, plus, writable properties (any of!)

    # @hybrid_property: readable, writable
    HYBRID_PROPERTY_R = auto()
    HYBRID_PROPERTY_W = auto()
    HYBRID_PROPERTY_RW = HYBRID_PROPERTY_R | HYBRID_PROPERTY_W  # any

    # relationship()s
    RELATIONSHIP = auto()
    DYNAMIC_LOADER = auto()

    # association_proxy()
    ASSOCIATION_PROXY = auto()

    # composite() of multiple columns
    COMPOSITE = auto()

    # column_property() expressions
    EXPRESSION = auto()

    # @hybrid_method()
    HYBRID_METHOD = auto()

    # Custom method for application-specific fields.
    # For your convenience.
    APPLICATION_CUSTOM = auto()

    # Collections
    ALL_COLUMNS = COLUMN | COMPOSITE | EXPRESSION
    ALL_PROPERTIES = PROPERTY_RW | HYBRID_PROPERTY_RW
    ALL_LOCAL_FIELDS = ALL_COLUMNS | ALL_PROPERTIES  # everything you can get without joining, without HYBRID_METHOD
    ALL_RELATIONSHIPS = RELATIONSHIP | ASSOCIATION_PROXY  # note: no dynamic loader here (safeguard: these can be large!)
    ALL = ALL_LOCAL_FIELDS | ALL_RELATIONSHIPS | DYNAMIC_LOADER | HYBRID_METHOD | APPLICATION_CUSTOM
