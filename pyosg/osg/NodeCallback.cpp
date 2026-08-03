#include "NodeCallback.hpp"

namespace pyosg {

void bind_NodeCallback(py::module_& m) {
	// osg::Callback is NodeCallback's REAL base (osg::NodeCallback : public virtual osg::Callback,
	// see osg/Callback) -- registered here, not just skipped straight to osg::Object, because
	// other modules (osgx's FlyToCallback/ShakeCallback, osgx/CameraIntents.hpp) derive directly
	// from osg::Callback and need it as a real registered pybind base for that to work. Bound with
	// the detail::Callback trampoline (see NodeCallback.hpp) so a Python subclass overriding run()
	// actually dispatches through real C++ virtual calls, not just direct Python method lookup.
	py::class_<
		osg::Callback,
		detail::Callback,
		osg::Object,
		osg::ref_ptr<osg::Callback>
	>(m, "Callback")
		.def(py::init<>())
	;

	py::class_<
		osg::NodeCallback,
		detail::NodeCallback,
		osg::Callback,
		osg::ref_ptr<osg::NodeCallback>
	>(m, "NodeCallback")
		.def(py::init<>())
	;
}

}
