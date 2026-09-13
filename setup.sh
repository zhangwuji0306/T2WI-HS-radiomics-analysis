#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python3.7}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python 3.7 is required. Pin Python 3.7 in the Codex cloud environment settings." >&2
  exit 1
fi

PYTHON_VERSION="$($PYTHON_BIN -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])')"
case "$PYTHON_VERSION" in
  3.7.*) ;;
  *)
    echo "Expected Python 3.7.x, found $PYTHON_VERSION." >&2
    exit 1
    ;;
esac

"$PYTHON_BIN" -m pip install --disable-pip-version-check --user -r requirements-cloud.txt

"$PYTHON_BIN" -c "import SimpleITK, matplotlib, numpy, pandas, pywt, radiomics, scipy, sklearn, yaml; print('Codex cloud dependencies verified with Python', __import__('sys').version.split()[0])"
