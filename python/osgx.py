"""Compatibility import for the osgx bindings packaged with OpenSceneGraph.

New code can use ``OpenSceneGraph.osgx``. Retain the historical top-level
module while downstream projects migrate.
"""

from OpenSceneGraph.osgx import * # noqa: F401,F403
