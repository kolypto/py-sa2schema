from typing import Generic

# Python >= 3.8
try:
    from typing import Literal, get_args, get_origin
# Compatibility
except ImportError:
    # Fake `Literal` for older Pythons
    from typing import _SpecialForm
    class Literal(type):
        @classmethod
        def __getitem__(self, item):
            return self

    get_args = lambda t: getattr(t, '__args__', ()) if t is not Generic else Generic
    get_origin = lambda t: getattr(t, '__origin__', None)
