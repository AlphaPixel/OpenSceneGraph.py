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

# TODO

- [ ] All of the corresponding "math" bindings; can the GLM python module serve in the interim?
- [x] GUIEventHandler
- [x] NodeCallback
- [ ] Drawable/DrawCallback (tricky due to rendering pipeline and non-copyable args)
- [ ] CameraManipulator (multimethod override, multiple overloads, non-copyable args)
- [ ] Operation
- [x] Basic osgViewer::Viewer demo
