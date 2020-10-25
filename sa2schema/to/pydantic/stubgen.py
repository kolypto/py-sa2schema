""" Generate stub files for Pydantic models """
from __future__ import annotations

import ast
import typing
from dataclasses import dataclass
from typing import Type, Collection

import pydantic as pd

from sa2schema.stubgen import ModelFieldInfo, ModelInfo as _ModelInfo, merge_imports


def stubs_for_pydantic(models: Collection[Type[pd.BaseModel]], clsname: str = None) -> ast.Module:
    """ Generate stubs for Pydantic models

    Example:
        ast.unparse(stubs_for_models([db.User]))
    """
    model_infos = [ModelInfo.from_pydantic_model(model) for model in models]
    ast_models = [model_info.to_ast() for model_info in model_infos]
    ast_imports = merge_imports(model_infos).to_ast()

    if clsname:
        ast_models = [
            ast.ClassDef(
                clsname,
                bases=[],
                decorator_list=[],
                keywords=[],
                body=ast_models
            )
        ]

    return ast.Module(
        [
            ast.ImportFrom('__future__', [ast.alias('annotations')], level=0),
            ast.Import([ast.alias('pydantic')]),
            ast_imports,
            ast.parse('NoneType = type(None)'),
            *ast_models,
        ],
        type_ignores=[]
    )


@dataclass
class ModelInfo(_ModelInfo):
    @classmethod
    def from_pydantic_model(cls, model: Type[pd.BaseModel]):
        """ Extract structural information from a pydantic model """
        return cls(
            name=model.__name__,
            docstring=model.__doc__ or '',
            bases=[pd.BaseModel],
            fields=[
                ModelFieldInfo(
                    name=name,
                    type=typing.Optional[field.outer_type_] if field.allow_none else field.outer_type_,
                    comment=field.field_info.title or '',
                )
                for name, field in model.__fields__.items()
            ]
        )
