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

		if(kwargs.contains("cullingActive")) self.setCullingActive(
			kwargs["cullingActive"].cast<bool>()
		);
	}
}

namespace pyosg {

void bind_Node(py::module_& m) {
	auto node = py::class_<osg::Node, osg::Object, osg::ref_ptr<osg::Node>>(m, "Node")
		.def(py::init<>())
		.def(py::init(pyx::kwargs_ctor<osg::Node>()))
		.def_property(
			"updateCallback",
			detail::NodeSlots::getter<detail::UpdateCallbackSlot>(detail::UpdateCallbackGetter),
			detail::node_update_callback_property_setter()
		)
		.def("accept", [](osg::Node& self, osg::NodeVisitor* nv) { self.accept(*nv); })
		.def_property(
			"stateSet",
			py::cpp_function(
				[](osg::Node& self) { return self.getOrCreateStateSet(); },
				py::return_value_policy::reference
			),
			[](osg::Node& self, osg::StateSet* ss) { self.setStateSet(ss); }
		)
		.def_property("nodeMask", &osg::Node::getNodeMask, &osg::Node::setNodeMask)
		.def_property(
			"cullingActive",
			&osg::Node::getCullingActive,
			&osg::Node::setCullingActive
		)
		.def_property(
			"initialBound",
			py::cpp_function(
				&osg::Node::getInitialBound,
				py::return_value_policy::reference_internal
			),
			&osg::Node::setInitialBound
		)
		.def("dirtyBound", &osg::Node::dirtyBound)
		.def("computeBound", &osg::Node::computeBound)
		.def_property_readonly(
			"bound",
			&osg::Node::getBound,
			py::return_value_policy::reference_internal
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
	}, py::return_value_policy::reference, "node"_a);
}

}
