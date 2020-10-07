#! /usr/bin/env bash
set -e -u -x

function repair_wheel {
    wheel="$1"
    if ! auditwheel show "$wheel"; then
        echo "Skipping non-platform wheel $wheel"
    else
        auditwheel repair "$wheel" --plat "$PLAT" -w /io/wheelhouse/
    fi
}

#
## Install a system package required by our library
yum install -y atlas-devel

# Compile wheels
SUPPORTED_PYTHONS=(
  "/opt/python/cp37-cp37m/bin"
  "/opt/python/cp38-cp38/bin"
  "/opt/python/cp39-cp39/bin"
)

for PYBIN in "${SUPPORTED_PYTHONS[@]}" ; do
  cd /io
  "${PYBIN}/pip" install poetry
  "${PYBIN}/poetry" build
  #    "${PYBIN}/pip" wheel /io/ --no-deps -w wheelhouse/
done

# Bundle external shared libraries into the wheels
for whl in dist/*.whl; do
    repair_wheel "$whl"
done

# Install packages and test
for PYBIN in "${SUPPORTED_PYTHONS[@]}" ; do
  "$PYBIN/poetry" install --no-dev --no-root
  "$PYBIN/poetry" run pip install sa2schema --no-index -f /io/dist
  "$PYBIN/poetry" run pytest

  cd /io
  "${PYBIN}/pytest"
done
