"""Public Python package for the OpenSceneGraph native bindings.

The compiled implementation remains private so this package can grow Python
helpers, utilities, and examples without changing the public import surface.
"""

import os as _os
from pathlib import Path as _Path

# The core extension's directory contains the project-built OSG DLLs and ktx.
# osgDB loads format plugins from its child directory later; on Windows those
# plugins need their parent DLL directory in the process search path too.
_dll_directory = None
if hasattr(_os, "add_dll_directory"):
	_dll_directory = _os.add_dll_directory(str(_Path(__file__).parent))

from ._OpenSceneGraph import * # noqa: F401,F403
from . import _OpenSceneGraph as _native

import sys as _sys

# The native extension creates these submodules. Publish them under their
# long-standing public paths, so both old and package-style imports work.
for _name in ("osg", "osgAnimation", "osgUtil", "osgDB", "osgGA", "osgViewer", "GL"):
	_sys.modules[f"{__name__}.{_name}"] = getattr(_native, _name)

__all__ = [name for name in dir(_native) if not name.startswith("_")]

del _name, _native, _sys, _os, _Path
