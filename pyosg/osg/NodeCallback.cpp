#include "NodeCallback.hpp"

namespace pyosg {

void bind_NodeCallback(py::module_& m) {
	// osg::Callback is NodeCallback's REAL base (osg::NodeCallback : public virtual osg::Callback,
	// see osg/Callback) -- registered here, not just skipped straight to osg::Object, because
	// other modules (osgx's FlyToCallback/ShakeCallback, osgx/CameraIntents.hpp) derive directly
	// from osg::Callback and need it as a real registered pybind base for that to work. No
	// trampoline: nothing needs a Python-side override of run() at the raw Callback level (yet --
	// that's the deferred pyx::CallableCallback bool(Args...) work).
	py::class_<
		osg::Callback,
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
