""" Pydantic schema tools """

from typing import Type, Iterable

import pydantic as pd

from .annotations import ModelT


def derive_model(model: ModelT,
                 model_name: str,
                 include: Iterable[str] = None,
                 exclude: Iterable[str] = None,
                 ) -> Type[pd.BaseModel]:
    """ Derive a Pydantic model by including/excluding fields

    Args:
        model: Pydantic model to derive from
        model_name: Name for the new model
        include: The list of fields to include into the resulting model. All the rest will be excluded.
        exclude: The list of fields to exclude from the resulting model. All the rest will be included.
    """
    assert bool(include) != bool(exclude), 'Provide `include` or `exclude` but not both'

    # Prepare include list
    include_fields = set(include) if include else (set(model.__fields__) - set(exclude))

    # Fields
    fields = {
        name: (field.type_, field.field_info)
        for name, field in model.__fields__.items()
        if name in include_fields
    }

    # Derive a model
    return pd.create_model(
        model_name,
        __config__=model.__config__,
        # __base__=model,  # NOTE: we do not do inheritance because it picks up the fields from the base model
        __module__=model.__module__,  # will this work?
        **fields
    )
