# TLDR

If something is misbehaving and you don't want to [read the Overview](Overview),
it's likely one of these things:

- Are you using `py::return_value_policy::reference*` correctly when returning a
  pointer/reference to another wrapped object?
- If you're ACCEPTING a wrapped object, are you using `py::keep_alive<>` (if
  necessary)?
- If an instance is constructed in C++ but needs to support virtual method
  override by derived classes in Python, you must make use of a "trampoline." In
  some cases simply calling `PYBIND_OVERRIDE{_PURE}` will be enough; if not,
  [refer to the comments](src/osg.hpp#84) of `pyosg::detail::call_override`.

# Overview

Slowly migrating existing research/code/attempts into this repository to build a
solid foundation for moving forward. I'd like to establish a sound base (coding
style, binding methodology, warnings-as-errors, static analysis, valgrind/ASAN
support, etc) so that ANYONE can jump in and contribute.

**NOTE**: During development, we need to continually ask the question "how can
existing/established projects--that already use OSG--leverage OUR headers to
simplify creating their OWN bindings?" This will mean that we need to keep
things modular, support `pybind11::import_`, and export ALL of the utility
functions and *"trampoline"* wrappers necessary for any external project to
include and utilize.

**NOTE**: In addition to the above, it may become necessary at SOME POINT to
create a kind of "shared core" library that both these bindings **AND** others
link to in order to resolve utility/trampoline bits. For example, if a user
wants to create Python bindings for their existing product (`osgAcme`), they
can/should be able to do something like the following:

```
// First, they'll kick off an import to make pybind11 aware of all the types
// defined in this project:
py::module_::import("OpenSceneGraph");

// If the above was successful, pybind11 will understand and handle inheritance
// such as this:
py::class_<osgAcme::Foo, osg::Group, osg::ref_ptr<osgAcme::Foo>>(m, "Foo")
	.def(py::init<>())
;

// Inevitably, the osgAcme bindings will want to use something we had to
// "trampoline" for pybind11 to build properly (essentially ANYTHING with
// virtual methods that need to work both in Python AND C++):
py::class_<
    osgAcme::EventHandler,
    pyosgGA::GUIEventHandler,
    osg::ref_ptr<osgAcme::EventHandler>
>(m, "EventHandler")
    .def("method", ...)
    .def_property("property", ...)
    // Continues...
;
```

In the above, notice how we use `pyosgGA::GUIEventHandler` (instead of
`osgGA::GUIEventHandler`) in the template parameters; this is **REQUIRED** (a
"trampoline") in order for virtual overrides--defined in Python--to interop with
C++ and pybind11 correctly. The "shared core" mentioned above would provide both
the headers AND the static library for linker resolution (used by both this
OpenSceneGraph.so module and the hypothetical osgAcme.so module).

# Cheatsheet

## keep_alive

The pybind API calls the template parameters `py::keep_alive<Nurse, Patient>`.
Once you understand *why* it uses these names (and understand WHAT the numeric
indices refer to), using `py::keep_alive<>` becomes a lot easier: a `Nurse`
keeps a `Patient` alive.

### Indices

| Index | Refers to                     |
| ----- | ----------------------------- |
| `0`   | the **return value** (if any) |
| `1`   | `self` (for methods)          |
| `2`   | first explicit argument       |
| `3`   | second explicit argument      |
| ...   | etc                           |

### Common Usage

| Pattern            | Meaning                | Typical Use                    |
| ------------------ | ---------------------- | ------------------------------ |
| `keep_alive<1, 2>` | self owns arg          | containers, graphs             |
| `keep_alive<0, 1>` | return depends on self | views (arrays), internals      |
| `keep_alive<2, 1>` | arg owns self          | rare / suspect                 |

We could even come up with some aliases such as:

```
using KeepChildAlive = py::keep_alive<1, 2>;
using KeepSelfAlive  = py::keep_alive<0, 1>;
```
## return_value_policy

Use `reference_internal` when:

- returning userData
- returning parents / children
- returning anything owned by self

Essentially, the returned object’s lifetime is tied to the parent (self) through
`keep_alive<0, 1>()`.

Use `reference` when:

- returning globally-owned singletons
- returning objects guaranteed to outlive Python
- you want raw semantics

The returned object is not dependent on self.

A great example of `reference` vs `reference_internal` are the
`Node.updateCallback` and `Node.stateSet` properties.

Avoid `copy`, `move`, and `take_ownership` unless the C++ API explicitly
documents ownership transfer.

# TODO (General)

- [ ] Solidify make_list/make_tuple vs py::make_tuple
- [ ] Add "buffer protocol" support for Vec/Matrix objects
- [ ] Replace every instance of `std::runtime_error` with something... better
- [ ] Settle on a single `py::obect` vs `const py::args&` function argument style
- [ ] Threading support (see below)
- [ ] Math
  - [x] Vec
  - [ ] Quat
  - [x] Matrix
- [ ] Array interfaces
- [ ] Geometry
- [x] GUIEventHandler
- [x] NodeCallback
- [ ] Drawable/DrawCallback (tricky due to rendering pipeline and non-copyable args)
- [ ] CameraManipulator (multimethod override, multiple overloads, non-copyable args)
- [ ] Operation
- [x] Basic osgViewer::Viewer demo
- [ ] Demo secondary bindings **BASED ON** these

## TODO (Specific)

- [ ] Make sure all `py::arg` use `""_a` syntax instead.
- [ ] Make sure all `py::enum_` use `export_values()` if necessary.
- [ ] Add docstrings!

## TODO (Threading) **IMPORTANT!!!**

This is going to be a HUGE headache, no matter WHAT we do. For now, we should
**ENFORCE** a `SingleThreaded` model. Later, in order to FULLY support
multithreaded processing, we'll need to utilize some kind of "event queue" or
similar; Python has LONG be notorious for very poor paralellism when interacting
with C/C++ extension modules.

## TODO (Secondary Demo)

Python bindings are great on their own, but a **really** great feature to have
would be exposing an API that also *embeds* the Python interpreter directly into
an existing application in a seamless manner, removing the need to rely on any
external Python installation environments.
