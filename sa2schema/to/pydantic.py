""" SA-Pydantic bridge between SqlAlchemy and Pydantic """
from typing import Container, TypeVar, Tuple, Dict, Union, Callable
from pydantic import BaseModel, BaseConfig, create_model, Field, Required
from pydantic.fields import Undefined
from sqlalchemy.ext.declarative import DeclarativeMeta

from sa2schema import AttributeType, sa_model_info
from sa2schema.attribute_info import AttributeInfo, NOT_PROVIDED, SAAttributeType


class SAModel(BaseModel):
    class Config(BaseConfig):
        orm_mode = True


ModelT = TypeVar('ModelT')


def sa_model(Model: DeclarativeMeta, *,
             Parent: ModelT = SAModel,
             types: AttributeType = AttributeType.COLUMN,
             only_readable: bool = False,
             only_writable: bool = False,
             exclude: Union[Callable[[str, SAAttributeType], bool], Container[str]] = (),
             ) -> ModelT:
    """ Create a Pydantic model from an SqlAlchemy model

    It will go through all attributes of the given SqlAlchemy model and use this information to create fields:
    attribute name, column type, its default value, nullability, and docstring.
    It can even extract the types of @property and @hybrid_property fields, if you've annotated their return types.

    If any attribute of the SqlAlchemy model has a type hint, it will be used instead of the column type.
    Use this approach if sa_model() guessed any of the types incorrectly.

    Args:
        Model: the SqlAlchemy model to convert
        Parent: base Pydantic model to use for a subclassed SqlAlchemy model. Use it to provide Config class
        types: attribute types to include. See AttributeType
        only_readable: only include fields that are readable. Useful for output models.
        only_writable: only include fields that are writable. Useful for input models.
        exclude: the list of fields to ignore, or a filter(name, attribute) to exclude fields dynamically
    Returns:
        Pydantic model class
    """
    # Create the model
    pd_model = create_model(
        __model_name=Model.__name__,
        __base__=Parent,
        **sa_model_fields(Model, types=types, exclude=exclude,
                          only_readable=only_readable, only_writable=only_writable)
    )
    pd_model.__doc__ = Model.__doc__
    return pd_model


def sa_model_fields(Model: DeclarativeMeta, *,
                    types: AttributeType = AttributeType.COLUMN,
                    only_readable: bool = False,
                    only_writable: bool = False,
                    exclude: Union[Callable[[str, SAAttributeType], bool], Container[str]] = (),
                    can_omit_nullable: bool = True,
                    ) -> Dict[str, Tuple[type, Field]]:
    """ Take an SqlAlchemy model and generate pydantic Field()s from it

    It will use sa_model_info() to extract attribute information from the SqlAlchemy model.
    Only fields selected by `types` & `exclude` will be considered.
    If SqlAlchemy model contains type annotations, they will override column types.

    Args:
        Model: the model to generate fields from
        types: attribute types to include. See AttributeType
        only_readable: only include fields that are readable
        only_writable: only include fields that are writable
        exclude: the list of fields to ignore, or a filter(name, attribute) to exclude fields dynamically
        can_omit_nullable: `False` to make nullable fields and fields with defaults required.
    Returns:
        a dict: attribute names => (type, Field)
    """
    # Model annotations will override any Column types
    model_annotations = Model.__annotations__

    # Walk attributes and generate Field()s
    return {
        name: (
            # Field type
            model_annotations.get(
                # try to get the type override
                name,
                # fall back to annotation types
                info.final_value_type
            ),
            # Field() object
            make_field(info, can_omit_nullable),
        )
        for name, info in sa_model_info(Model, types=types, exclude=exclude).items()
        if (not only_readable or info.readable) and
           (not only_writable or info.writable)
    }


def make_field(attr_info: AttributeInfo, can_omit_nullable: bool = True) -> Field:
    """ Create a Pydantic Field() from an AttributeInfo """
    # Pydantic uses `Required = ...` to indicate which nullable fields are required
    # `Undefined` for nullable fields will result in `None` being the default
    no_default = Undefined if can_omit_nullable else Required
    return Field(
        default=no_default
                if attr_info.default is NOT_PROVIDED else
                attr_info.default,
        alias=None,  # sqlalchemy synonyms are installed later on
        title=attr_info.doc,  # `title` seems fine. `description` can be used for more verbose stuff
        const=not attr_info.writable,
    )


# TODO: class with namespace and automatic references
