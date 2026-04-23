# Key Features (April, 2026)

- Covers most of the core `osg` namespace, as well as significant portions of
  `osgViewer`, `osgUtil`, `osgGA`, and `osgDB`. Any missing or unwrapped
  objects can be added quickly as needed.

- Implements only the modern, non-FFP parts of OpenSceneGraph; all testing is
  done with GL3/GLCORE as the minimum target.

- Works in both modular *and* embedded setups. In an embedded build, the entire
  `OpenSceneGraph.py` module interface can be **compiled into** the resulting
  library or binary, making packaging and deployment much simpler.

- Provides solutions to some of the sharp edges involved in wrapping
  intrusively reference-counted code, especially *object lifetime*. In many
  `pybind11` bindings, wrapper code must rely heavily on `keep_alive<>` in
  order to guarantee object lifetime, which can lead to memory bloat and object
  accumulation throughout the life of the process. `OpenSceneGraph.py` uses a
  different approach in which the owning `PyObject*` reference is **stored
  inside the `UserDataContainer`** of the instance, so when something is
  deleted or reassigned, it can truly be deallocated.

- Preserves **stable Python identity** for C++ object instances, even when
  those objects are accessed repeatedly through container proxies or property
  getters. This avoids one of the most common and confusing failure modes in
  C++/Python bindings: multiple Python wrapper objects referring to the same
  underlying C++ instance without behaving like the “same object” at the Python
  level.

- Uses a **unified proxy architecture** across intrusive reference-counted
  objects, shared-ownership objects, sequence-style containers, mapping-style
  containers, and persistent property-backed references. This keeps the Python
  API consistent while still respecting native ownership and lifetime rules.

- Overhauls the OSG interface, making it naturally Pythonic and substantially
  more pleasant to work with. Instead of binding the OSG API 1:1,
  `OpenSceneGraph.py` exposes semantic proxies over things like `osg::Group`,
  `osg::Geode`, `osg::Geometry`, and more. For example:

  ```py
  # Instead of this...
  g = osg.Group()
  g.addChild(osg.Node())
  g.addChild(osg.Node())
  g.addChild(osg.Node())

  # ...you instead do something like:
  g = osg.Group(name="Group", children=(
      osg.Geode(name="Geode_00"),
      osg.Node(name="Node_00", debug=True),
      osg.Node(),
  ))

  g.children[0].drawables.extend((
      osg.Geometry(),
      osg.ShapeDrawable(),
      # ...etc...
  ))
  ```

  [!NOTE]
  > Wherever it is practical to improve the ergonomics of the aging OSG API in
  > Python, we do. Most attributes can be set both at construction time and
  > through traditional setter-based APIs. Likewise, anything that functions as
  > a callback in OSG can usually be supplied either through the traditional
  > method-override approach or by simply passing any suitable Python
  > callable.

- Container-like APIs are backed by semantic proxies, not thin wrappers. These
  preserve object identity, native behavior, and ownership rules while
  supporting natural Python idioms such as indexing, iteration, mutation,
  appending, extending, and keyword-based construction.

- Provides a robust callback binding system supporting both Python subclass
  overrides and plain Python callables/lambdas for OSG callback types.
  Traversal semantics are preserved correctly, so native OSG behavior is not
  replaced by a Python-specific approximation.

- Object instances pass cleanly across the Python/C++ boundary; anything created
  in one environment can be accessed directly and used in the other.

- Designed for incremental embedding into existing C++ OSG applications. Python
  can be introduced as a scripting/runtime layer without requiring an all-Python
  rewrite of the existing codebase.

- All of the OpenSceneGraph.py headers are exposed, allowing any existing
  codebase to adapt its current stack so that it works inside OpenSceneGraph.py
  natively. Helpers, trampoline classes, proxy machinery, and related
  infrastructure are all accessible from C++.

- Makes wide use of the buffer protocol, meaning data coming from libraries like
  NumPy or PyTorch can be passed to and visualized with OpenSceneGraph.py with
  almost no copying of data. This also works in reverse: data from
  OpenSceneGraph.py can be sent to NumPy, PyTorch, and similar libraries with
  little to no copying.

- Supports modern interactive and asynchronous workflows, including cooperative
  asyncio integration, background task execution, progress/event queues, and
  clean cross-language cancellation and shutdown patterns.

- Perhaps best of all: OpenSceneGraph.py can be used INTERACTIVELY. You can fire
  up something like ipython, interactively add objects to your scene, modify
  attributes, change object internals, and watch it all take effect
  immediately--including the entire Program / Shader pipeline.

# Examples

- [Render To Texture](examples/pyosg-rtt.py): Demonstrates how to setup a
  standard colorbuffer + depthbuffer rendering pipeline, composited together
  using the standard fullscreen-quad approach.

- [Point Visualization](examples/pyosg-points.py): Visualizes random data
  created by NumPy as simple points.

- [IPython Interactive REPL](examples/pyosg-repl.py): Fires up an `ipython3`
  REPL session with `OpenSceneGraph` imported and ready to use!

- [OSG + Async](examples/pyosg-async.py): A simple example demonstrating modern
  Python `async/await` programming in OpenSceneGraph.py.
