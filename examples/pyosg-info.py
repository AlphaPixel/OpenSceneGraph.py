import pkgutil
import openscenegraph

package = openscenegraph
# This will walk through every sub-package and submodule
for info in pkgutil.walk_packages(package.__path__, prefix=package.__name__ + "."):
    print(info.name)
