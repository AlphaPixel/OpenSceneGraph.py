"""Public Python package for the OpenSceneGraph native bindings.

The compiled implementation remains private so this package can grow Python
helpers, utilities, and examples without changing the public import surface.
"""

from ._OpenSceneGraph import * # noqa: F401,F403
from . import _OpenSceneGraph as _native

import sys as _sys

# The native extension creates these submodules. Publish them under their
# long-standing public paths, so both old and package-style imports work.
for _name in ("osg", "osgAnimation", "osgUtil", "osgDB", "osgGA", "osgViewer", "GL"):
	_sys.modules[f"{__name__}.{_name}"] = getattr(_native, _name)

__all__ = [name for name in dir(_native) if not name.startswith("_")]

del _name, _native, _sys
