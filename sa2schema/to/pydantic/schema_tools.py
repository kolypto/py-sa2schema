""" Pydantic schema tools """

from typing import Type, Iterable, Optional, Mapping, Any

import pydantic as pd

from .annotations import PydanticModelT


def derive_model(model: PydanticModelT,
                 model_name: str,
                 include: Iterable[str] = None,
                 exclude: Iterable[str] = None,
                 BaseModel: Optional[PydanticModelT] = None,
                 extra_fields: Mapping[str, Any] = None,
                 ) -> Type[pd.BaseModel]:
    """ Derive a Pydantic model by including/excluding fields

    Args:
        model: Pydantic model to derive from
        model_name: Name for the new model
        include: The list of fields to include into the resulting model. All the rest will be excluded.
        exclude: The list of fields to exclude from the resulting model. All the rest will be included.
        BaseModel: the base to use
        extra_fields: extra fields to add. They will override existing ones.
    """
    assert bool(include) != bool(exclude), 'Provide `include` or `exclude` but not both'

    # Prepare include list
    include_fields = set(include) if include else (set(model.__fields__) - set(exclude))

    # Fields
    field: pd.fields.ModelField
    fields = {
        name: (
            field.type_ if field.required else Optional[field.type_],
            field.field_info
        )
        for name, field in model.__fields__.items()
        if name in include_fields
    }

    # Add/override extra fields
    fields.update(extra_fields or {})

    # Derive a model
    return pd.create_model(
        model_name,
        __module__=model.__module__,  # will this work?
        # Use `BaseModel` and its config if provided.
        # If not, take __config__ from the `model`
        __config__=None if BaseModel else model.__config__,
        __base__=BaseModel,
        **fields
    )
