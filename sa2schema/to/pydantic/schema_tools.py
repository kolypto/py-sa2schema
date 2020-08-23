""" Pydantic schema tools """

from typing import Type, Iterable

import pydantic as pd


def derive_model(model: Type[pd.BaseModel],
                 model_name: str,
                 include: Iterable[str] = None,
                 exclude: Iterable[str] = None,
                 ) -> Type[pd.BaseModel]:
    """ Derive a Pydantic model by including/excluding fields """
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
