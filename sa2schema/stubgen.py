""" Generate stub files for Pydantic models """
from __future__ import annotations

import ast
import typing
from dataclasses import dataclass, field
from typing import List, Any, Type, Collection, Set

import pydantic as pd

from sa2schema import sa_model_info
from sa2schema.pluck import AttributeType


def stubs_for_sa_models(models: Collection[Type[pd.BaseModel]]) -> ast.Module:
    """ Generate stubs for SqlAlchemy models

    Example:
        ast.unparse(stubs_for_models([db.User]))
    """
    model_infos = [ModelInfo.from_sa_model(model) for model in models]
    ast_models = [model_info.to_ast() for model_info in model_infos]
    ast_imports = merge_imports(model_infos).to_ast()

    return ast.Module(
        [
            ast.ImportFrom('__future__', [ast.alias('annotations')], level=0),
            ast_imports,
            ast.parse('NoneType = type(None)'),
            *ast_models,
        ],
        type_ignores=[]
    )


def merge_imports(models: Collection[ModelInfo]) -> ImportInfo:
    """ Collect imports from many models and merge them into one

    Note: only do it after to_ast() has been called on them
    """
    module_names = set(
        module_name
        for model in models
        for field in model.fields
        for module_name in field.import_modules
    )
    return ImportInfo(sorted(module_names))


@dataclass
class ModelInfo:
    """ Structural information of a class """
    name: str
    docstring: str
    fields: List[ModelFieldInfo]
    bases: List[type] = field(default_factory=list)

    @classmethod
    def from_sa_model(cls, model: type):
        """ Extract structural information from a pydantic model """
        info = sa_model_info(model, types=AttributeType.ALL)
        return cls(
            name=model.__name__,
            docstring=model.__doc__ or '',
            fields=[
                ModelFieldInfo(
                    name=name,
                    type=attr_info.final_value_type,
                    comment=attr_info.doc,
                )
                for name, attr_info in info.items()
            ]
        )

    def to_ast(self) -> ast.ClassDef:
        """ Generate Python AST for this model info """
        return ast.ClassDef(
            self.name,
            bases=[
                ast.Attribute(ast.Name(base.__module__), base.__name__)
                for base in self.bases
            ],
            decorator_list=[],
            keywords=[],
            body=[
                # Docstring
                ast.Expr(ast.Constant(self.docstring)),
                # Attributes
                *(
                    field.to_ast()
                    for field in self.fields
                )
            ]
        )


@dataclass
class ModelFieldInfo:
    """ Structural information of a class attribute """
    name: str
    type: Any
    comment: str

    import_modules: Set[ImportInfo] = field(default_factory=set)

    def to_ast(self) -> ast.AnnAssign:
        """ Generate Python AST for this field info """
        return ast.AnnAssign(
            ast.Name(self.name),
            ast.Name(self.get_type_name(self.type)),
            ast.Constant(...),
            simple=1
        )

    def get_type_name(self, type: Any) -> str:
        # Special case: forward reference
        if isinstance(type, typing.ForwardRef):
            return type.__forward_arg__

        # Get the module name and import it
        module_name = type.__module__
        self.import_modules.add(module_name)

        # Types wrapped with other types
        type_origin = typing.get_origin(type)
        if type_origin is not None:
            wrapper_name = self.get_type_name(type_origin)
            wrapper_args = ', '.join(self.get_type_name(arg) for arg in typing.get_args(type))
            return f'{wrapper_name}[{wrapper_args}]'
        # The `typing` module needs special handling
        elif module_name == 'typing':
            return str(type)
        # Everything else is quite simple: just use the type name
        else:
            # Get the type name
            type_name = type.__name__

            # Built-ins are always available; therefore, use plain names
            if module_name == 'builtins':
                # unqualified: just `int`
                return type_name
            # Everything else has to be fully qualified
            else:
                # qualified: like `app.src.defs.const.UserAccountType`
                return f'{module_name}.{type_name}'


@dataclass
class ImportInfo:
    """ Information about an import statement """
    module_names: Collection[str]

    def to_ast(self) -> ast.Import:
        return ast.Import([
            ast.alias(module_name)
            for module_name in self.module_names
        ])
