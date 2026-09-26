#include "NodeCallback.hpp"

namespace pyosg {

void bind_NodeCallback(py::module_& m) {
	// osg::Callback is NodeCallback's REAL base (osg::NodeCallback : public virtual osg::Callback,
	// see osg/Callback) - registered here, not just skipped straight to osg::Object, because
	// other modules (osgx's FlyToCallback/ShakeCallback, osgx/CameraIntents.hpp) derive directly
	// from osg::Callback and need it as a real registered pybind base for that to work. Bound with
	// the detail::Callback trampoline (see NodeCallback.hpp) so a Python subclass overriding run()
	// actually dispatches through real C++ virtual calls, not just direct Python method lookup.
	auto callback = py::class_<
		osg::Callback,
		detail::Callback,
		osg::Object,
		osg::ref_ptr<osg::Callback>
	>(
		m,
		"Callback",
		"Base class for anything invoked during scene graph traversal (update, event, cull). "
		".nestedCallbacks is a sequence proxy over the chained callback list, rather than "
		"addNestedCallback()/removeNestedCallback()/getNestedCallback()."
	);

	// callback.nestedCallbacks - list view over the singly-linked nestedCallback chain (see
	// SequenceTraits<osg::Callback, NestedCallbacksTag> in NodeCallback.hpp): indexing, len(),
	// append(), insert(i, cb), del callback.nestedCallbacks[i], .remove(cb), .index(cb),
	// iteration - the usual SequenceProxy surface, instead of hand-walking getNestedCallback()
	// chains or calling addNestedCallback()/removeNestedCallback() directly.
	pyx::bind_proxy_property<detail::NestedCallbacksProxy, osg::Callback, detail::CallbackStorage>(
		callback, "_NestedCallbacks", "nestedCallbacks",
		"Sequence proxy over the chained callback list: indexing, len(), append(), insert(), "
		"del, remove(), index(), and iteration - in place of "
		"addNestedCallback()/removeNestedCallback()/getNestedCallback()."
	);

	// run()/__call__() below: a Python subclass (a trampoline) gets the base implementation, so
	// super().run()/super().__call__() never re-enter its own override; a C++ subclass dispatches
	// virtually.
	callback
		.def(py::init<>(), "Create a Callback with no nested callbacks.")
		.def("run", [](osg::Callback& self, osg::Object* object, osg::Object* data) {
			if(auto* nc = dynamic_cast<detail::NodeCallback*>(&self)) {
				return nc->osg::NodeCallback::run(object, data);
			}

			if(dynamic_cast<detail::Callback*>(&self)) return self.osg::Callback::run(object, data);

			return self.run(object, data);
		}, "object"_a, "data"_a,
			"Invoke this callback for object (e.g. a Node) with data (e.g. a NodeVisitor); the "
			"base implementation runs the nested callbacks."
		)
	;

	py::class_<
		osg::NodeCallback,
		detail::NodeCallback,
		osg::Callback,
		osg::ref_ptr<osg::NodeCallback>
	>(
		m,
		"NodeCallback",
		"A Callback specialized for Node.updateCallback/eventCallback, invoked once per "
		"traversal of the node it's attached to."
	)
		.def(py::init<>(), "Create a NodeCallback with no nested callbacks.")
		.def("__call__", [](osg::NodeCallback& self, osg::Node* node, osg::NodeVisitor* nv) {
			if(dynamic_cast<detail::NodeCallback*>(&self)) self.osg::NodeCallback::operator()(node, nv);

			else self(node, nv);
		}, "node"_a, "nv"_a,
			"Invoke this callback for node during nv's traversal; the base implementation "
			"continues the traversal (nested callbacks, then children)."
		)
	;
}

}
