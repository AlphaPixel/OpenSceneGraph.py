#include "Node.hpp"

namespace pybind11x {
	template<>
	void kwargs_init_own(osg::Node& self, const py::kwargs& kwargs) {
		if(kwargs.contains("nodeMask")) self.setNodeMask(
			kwargs["nodeMask"].cast<osg::Node::NodeMask>())
		;

		if(kwargs.contains("updateCallback")) pyosg::detail::node_update_callback_property_setter()(
			self,
			kwargs["updateCallback"]
		);

		if(kwargs.contains("eventCallback")) pyosg::detail::node_event_callback_property_setter()(
			self,
			kwargs["eventCallback"]
		);

		if(kwargs.contains("cullingActive")) self.setCullingActive(
			kwargs["cullingActive"].cast<bool>()
		);
	}
}

namespace pyosg {

void bind_Node(py::module_& m) {
	auto node = py::class_<osg::Node, osg::Object, osg::ref_ptr<osg::Node>>(
		m,
		"Node",
		"Base class for every element of the scene graph -- leaf Drawables and the Group "
		"nodes that hold them alike. .updateCallback/.eventCallback each accept either a "
		"NodeCallback subclass instance or a plain Python callable, in place of OSG's "
		"traditional set*Callback()/get*Callback() methods."
	)
		.def(py::init<>(), "Create a Node with default state (no name, all-visible nodeMask, no callbacks).")
		.def(
			py::init(pyx::kwargs_ctor<osg::Node>()),
			"Create a Node, setting any of nodeMask/updateCallback/eventCallback/cullingActive "
			"from keyword arguments."
		)
		.def_property(
			"updateCallback",
			detail::NodeSlots::getter<detail::UpdateCallbackSlot>(detail::UpdateCallbackGetter),
			detail::node_update_callback_property_setter(),
			"Callback (NodeCallback subclass instance or plain callable) invoked once per "
			"update traversal that visits this node."
		)
		.def_property(
			"eventCallback",
			detail::NodeSlots::getter<detail::EventCallbackSlot>(detail::EventCallbackGetter),
			detail::node_event_callback_property_setter(),
			"Callback (NodeCallback subclass instance or plain callable) invoked once per "
			"event traversal that visits this node."
		)
		.def("accept", [](osg::Node& self, osg::NodeVisitor* nv) { self.accept(*nv); },
			"Dispatch a NodeVisitor into this node, invoking the visitor's apply() and, if "
			"the traversal mode calls for it, recursing into children."
		)
		.def_property(
			"stateSet",
			py::cpp_function(
				[](osg::Node& self) { return self.getOrCreateStateSet(); },
				py::return_value_policy::reference
			),
			[](osg::Node& self, osg::StateSet* ss) { self.setStateSet(ss); },
			"This node's StateSet, created on first access if one doesn't exist yet "
			"(get-or-create semantics - see the module-level getStateSet() function for the "
			"non-creating variant)."
		)
		.def_property("nodeMask", &osg::Node::getNodeMask, &osg::Node::setNodeMask,
			"Traversal bitmask ANDed against a NodeVisitor's own traversalMask; zero means "
			"invisible to that traversal (culling, intersection, etc.)."
		)
		.def_property(
			"cullingActive",
			&osg::Node::getCullingActive,
			&osg::Node::setCullingActive,
			"Whether view-frustum/small-feature culling is applied to this node during the "
			"cull traversal."
		)
		.def_property(
			"initialBound",
			py::cpp_function(
				&osg::Node::getInitialBound,
				py::return_value_policy::reference_internal
			),
			&osg::Node::setInitialBound,
			"A user-supplied BoundingSphere unioned into computeBound()'s result, useful when "
			"a Drawable's true extent isn't known up front (e.g. procedural/GPU-generated geometry)."
		)
		.def("dirtyBound", &osg::Node::dirtyBound,
			"Mark this node's cached bounding sphere (and its parents', up the scene graph) "
			"stale, forcing recomputation on next access."
		)
		.def("computeBound", &osg::Node::computeBound,
			"Recompute and return this node's bounding sphere from its current content."
		)
		.def_property_readonly(
			"bound",
			&osg::Node::getBound,
			py::return_value_policy::reference_internal,
			"This node's cached BoundingSphere, recomputed lazily after dirtyBound()."
		)
	;

	node.attr("NodeMask") = detail::builtin_int();

	// Deliberately NOT a `Node` method/property, unlike `.stateSet` (which is the common,
	// get-or-create path). This is the rare, non-creating variant -- returns `None` rather than
	// forcing a `StateSet` into existence -- kept off `node.<TAB>` and matched to the
	// `osg.computeLocalToWorld(nodePath)`-style module-function precedent for "advanced, reach
	// for it deliberately" operations.
	m.def("getStateSet", [](osg::Node& self) -> osg::StateSet* {
		return self.getStateSet();
	}, py::return_value_policy::reference,
		"Return node's StateSet, or None if it doesn't have one - unlike node.stateSet, "
		"never creates one as a side effect.",
		"node"_a
	);
}

}
