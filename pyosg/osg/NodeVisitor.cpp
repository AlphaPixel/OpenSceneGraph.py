#include "NodeVisitor.hpp"

namespace pyosg {

void bind_NodeVisitor(py::module_& m) {
	// TODO: This _works_, but isn't really what we WANT; it'll return the pointers, exactly as
	// requested, but it doesn't do us much good in Python, unless we're just passing it directly
	// to something else (like the `osg::computeWorldToLocal` helpers).
	// py::bind_vector<std::vector<osg::Node*>>(m, "NodePath");

	// TODO: This is a readonly variant I'm testing!
	py::class_<osg::NodePath>(m, "NodePath")
		.def("__len__", [](const osg::NodePath& self) {
			return self.size();
		})
		.def("__repr__", [](const osg::NodePath& self) {
			std::ostringstream out;

			out << "NodePath[";

			for(std::size_t i = 0; i < self.size(); ++i) {
				if(i) { out << ", "; }

				out << self[i];
			}

			out << "]";

			return out.str();
		})
	;

	auto nv = py::class_<
		osg::NodeVisitor,
		detail::NodeVisitor,
		osg::Object,
		osg::ref_ptr<osg::NodeVisitor>
	>(m, "NodeVisitor");

	py::enum_<osg::NodeVisitor::TraversalMode>(nv, "TraversalMode")
		.value("TRAVERSE_NONE", osg::NodeVisitor::TRAVERSE_NONE)
		.value("TRAVERSE_PARENTS", osg::NodeVisitor::TRAVERSE_PARENTS)
		.value("TRAVERSE_ALL_CHILDREN", osg::NodeVisitor::TRAVERSE_ALL_CHILDREN)
		.value("TRAVERSE_ACTIVE_CHILDREN", osg::NodeVisitor::TRAVERSE_ACTIVE_CHILDREN)
	;

	py::enum_<osg::NodeVisitor::VisitorType>(nv, "VisitorType")
		.value("NODE_VISITOR", osg::NodeVisitor::NODE_VISITOR)
		.value("UPDATE_VISITOR", osg::NodeVisitor::UPDATE_VISITOR)
		.value("EVENT_VISITOR", osg::NodeVisitor::EVENT_VISITOR)
		.value("COLLECT_OCCLUDER_VISITOR", osg::NodeVisitor::COLLECT_OCCLUDER_VISITOR)
		.value("CULL_VISITOR", osg::NodeVisitor::CULL_VISITOR)
		.value("INTERSECTION_VISITOR", osg::NodeVisitor::INTERSECTION_VISITOR)
	;

	nv
		.def(
			py::init_alias<osg::NodeVisitor::TraversalMode>(),
			"traversalMode"_a=osg::NodeVisitor::TRAVERSE_NONE
		)
		.def("traverse", &osg::NodeVisitor::traverse, py::arg("node"))
		.def("_traverse", [](detail::NodeVisitor& self, osg::Node& node) {
			self._traverse(node);
		})
		.def("apply", py::overload_cast<osg::Node&>(&osg::NodeVisitor::apply))
		.def_property(
			"traversalMask",
			&osg::NodeVisitor::getTraversalMask,
			&osg::NodeVisitor::setTraversalMask
		)
		.def_property(
			"traversalMode",
			&osg::NodeVisitor::getTraversalMode,
			&osg::NodeVisitor::setTraversalMode
		)
		.def_property_readonly("frameStamp",
			py::overload_cast<>(&osg::NodeVisitor::getFrameStamp, py::const_),
			py::return_value_policy::reference
		)
		// TODO: See the comment for `bind_vector` above!
		.def_property_readonly(
			"nodePath",
			py::overload_cast<>(&osg::NodeVisitor::getNodePath, py::const_),
			py::return_value_policy::reference_internal
		)
	;
}

}
