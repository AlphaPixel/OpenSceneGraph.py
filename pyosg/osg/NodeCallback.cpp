#include "NodeCallback.hpp"

namespace pyosg {

void bind_NodeCallback(py::module_& m) {
	// osg::Callback is NodeCallback's REAL base (osg::NodeCallback : public virtual osg::Callback,
	// see osg/Callback) -- registered here, not just skipped straight to osg::Object, because
	// other modules (osgx's FlyToCallback/ShakeCallback, osgx/CameraIntents.hpp) derive directly
	// from osg::Callback and need it as a real registered pybind base for that to work. Bound with
	// the detail::Callback trampoline (see NodeCallback.hpp) so a Python subclass overriding run()
	// actually dispatches through real C++ virtual calls, not just direct Python method lookup.
	auto callback = py::class_<
		osg::Callback,
		detail::Callback,
		osg::Object,
		osg::ref_ptr<osg::Callback>
	>(m, "Callback");

	// callback.nestedCallbacks -- list view over the singly-linked nestedCallback chain (see
	// SequenceTraits<osg::Callback, NestedCallbacksTag> in NodeCallback.hpp): indexing, len(),
	// append(), insert(i, cb), del callback.nestedCallbacks[i], .remove(cb), .index(cb),
	// iteration -- the usual SequenceProxy surface, instead of hand-walking getNestedCallback()
	// chains or calling addNestedCallback()/removeNestedCallback() directly.
	pyx::bind_proxy_property<detail::NestedCallbacksProxy, osg::Callback, detail::CallbackStorage>(
		callback, "_NestedCallbacks", "nestedCallbacks"
	);

	callback
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
