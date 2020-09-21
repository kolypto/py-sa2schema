import os

# See if Cython is installed
try:
    from Cython.Build import cythonize
# Do nothing if Cython is not available
except ImportError:
    # Got to provide this function. Otherwise, poetry will fail
    def build(setup_kwargs):
        pass
# Cython is installed. Compile
else:
    import sys
    from setuptools import Extension
    from setuptools.dist import Distribution
    from distutils.command.build_ext import build_ext
    from shutil import which

    # You can also build it manually with:
    # $ cythonize -X language_level=3 -a -i sa2schema/pluck.py

    # This function will be executed in setup.py:
    def build(setup_kwargs):
        # Do nothing if setup.py is doing 'clean' or 'check', or 'SKIP_CYTHON' is explicitly given
        if 'clean' in sys.argv or 'check' in sys.argv or 'SKIP_CYTHON' in os.environ:
            return

        # Do nothing if `gcc` is not installed
        if which('gcc') is None:
            return

        # The file you want to compile
        extensions = [
            "sa2schema/pluck.py"
        ]

        # gcc arguments hack: enable optimizations
        os.environ['CFLAGS'] = '-O3'

        # Build
        setup_kwargs.update({
            'ext_modules': cythonize(
                extensions,
                language_level=3,
                compiler_directives={'linetrace': True},
            ),
            'cmdclass': {'build_ext': build_ext}
        })
