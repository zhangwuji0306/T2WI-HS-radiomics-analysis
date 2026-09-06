"""Verify the runtime versions required by the locked imaging environment."""

from __future__ import print_function

import importlib
import json
import platform
import sys


MODULES = {
    "numpy": "numpy",
    "pandas": "pandas",
    "openpyxl": "openpyxl",
    "scipy": "scipy",
    "scikit_learn": "sklearn",
    "matplotlib": "matplotlib",
    "pyyaml": "yaml",
    "pyradiomics": "radiomics",
    "simpleitk": "SimpleITK",
    "pywavelets": "pywt",
}


def main():
    expected = json.loads(sys.argv[1])
    actual = {"python": platform.python_version()}
    for key, module_name in MODULES.items():
        module = importlib.import_module(module_name)
        version = getattr(module, "__version__", None)
        if key == "simpleitk":
            version = module.Version_VersionString()
        actual[key] = str(version).lstrip("v")

    mismatches = {
        key: {"expected": expected[key], "actual": actual.get(key)}
        for key in expected
        if actual.get(key) != expected[key]
    }
    print(json.dumps({
        "environment": "t2_radiomics",
        "python": sys.executable,
        "versions": actual,
        "matches_locked_spec": not mismatches,
        "mismatches": mismatches,
    }, ensure_ascii=False, indent=2))
    return 1 if mismatches else 0


if __name__ == "__main__":
    sys.exit(main())
