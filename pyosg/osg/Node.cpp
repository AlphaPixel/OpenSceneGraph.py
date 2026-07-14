#include "Node.hpp"

namespace pyosg {

namespace detail {
	template<>
	void kwargs_init(osg::Node& self, const py::kwargs& kwargs) {
		kwargs_init(static_cast<osg::Object&>(self), kwargs);

		if(kwargs.contains("nodeMask")) self.setNodeMask(
			kwargs["nodeMask"].cast<osg::Node::NodeMask>())
		;

		if(kwargs.contains("updateCallback")) node_update_callback_property_setter()(
			self,
			// py::reinterpret_borrow<py::object>(kwargs["updateCallback"])
			kwargs["updateCallback"]
		);
	}
}

void bind_Node(py::module_& m) {
	auto node = py::class_<osg::Node, osg::Object, osg::ref_ptr<osg::Node>>(m, "Node")
		.def(py::init<>())
		// .def(py::init([](py::kwargs kwargs) -> osg::ref_ptr<osg::Node> {
		.def(py::init([](py::kwargs kwargs) {
			osg::ref_ptr<osg::Node> n = new osg::Node();

			detail::kwargs_init(*n, kwargs);

			return n;
		}))
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
}

}
