""" Pydantic schema tools """

from typing import Type, Iterable, Optional, Mapping, Any, Dict, Tuple

import pydantic as pd

from .annotations import PydanticModelT


def derive_model(model: PydanticModelT,
                 name: Optional[str] = None,
                 module: Optional[str] = None, *,
                 include: Iterable[str] = None,
                 exclude: Iterable[str] = None,
                 BaseModel: Optional[PydanticModelT] = None,
                 extra_fields: Mapping[str, Any] = None,
                 ) -> Type[pd.BaseModel]:
    """ Derive a Pydantic model by including/excluding fields

    Args:
        model: Pydantic model to derive from
        name: Name for the new model. None: get from the old model
            Note that in some cases non-unique model names may lead to errors. Try to provide a good one.
        module: __name__ of the module.
            Only important in cases where you want models to have globally unique names.
        include: The list of fields to include into the resulting model. All the rest will be excluded.
        exclude: The list of fields to exclude from the resulting model. All the rest will be included.
        BaseModel: the base to use
        extra_fields: extra fields to add. They will override existing ones.
    """
    assert bool(include) != bool(exclude), 'Provide `include` or `exclude` but not both'

    # Prepare include list
    include_fields = set(include) if include else (set(model.__fields__) - set(exclude))

    # Fields
    fields = prepare_fields_for_create_model(
        field
        for field in model.__fields__.values()
        if field.name in include_fields
    )

    # Add/override extra fields
    fields.update(extra_fields or {})

    # Default: `BaseModel` comes from the model itself
    if BaseModel is None:
        BaseModel = empty_model_subclass(model, f'{model.__name__}Derived')

    # Derive a model
    return pd.create_model(
        name or model.__name__,
        __module__=module or model.__module__,  # will this work?
        __base__=BaseModel,
        **fields
    )


def merge_models(name: str,
                 *models: PydanticModelT,
                 module: Optional[str] = None,
                 BaseModel: Optional[PydanticModelT] = None,
                 Config: Optional[type] = None,
                 extra_fields: Mapping[str, Any] = None,
                 ):
    # Collect fields
    fields = prepare_fields_for_create_model(
        field
        for model in models
        for field in model.__fields__.values()
    )

    # Add/override extra fields
    fields.update(extra_fields or {})

    # Create a model
    return pd.create_model(
        name,
        __module__=module or models[0].__module__,  # same module by default
        __config__=Config,
        __base__=BaseModel,
        **fields
    )


def empty_model_subclass(Model: PydanticModelT, name: str) -> PydanticModelT:
    """ Create a subclass of Model that will inherit none of the fields """
    return type(
        name,
        # Subclass the base model
        (Model,),
        # Reset the list of fields.
        # This is necessary so as not to inherit any fields from the base model
        {'__fields__': ()},
    )


def prepare_fields_for_create_model(fields: Iterable[pd.fields.ModelField]) -> Dict[str, Tuple[type, pd.fields.FieldInfo]]:
    return {
        field.name: (
            field.outer_type_ if field.required else Optional[field.type_],
            field.field_info
        )
        for field in fields
    }
