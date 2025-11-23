#include "../OpenSceneGraph-python.hpp"
#include "../osg.hpp"

PYOSG_DISABLE_WARNINGS

#include <osg/Group>

PYOSG_ENABLE_WARNINGS

namespace pyosg {

namespace detail {
	class NodeVisitor: public osg::NodeVisitor {
	public:
		using osg::NodeVisitor::NodeVisitor;

		// Trampoline-only helper: safe traversal entry that never re-enters Python
		// while Python apply() is active.
		void _traverse(osg::Node& node) {
			osg::NodeVisitor::traverse(node);
		}

		void apply(osg::Node& node) override {
			// Optional logging: keep or delete.
			std::cout
				<< "detail::NodeVisitor::apply(Node&)"
				<< " this=" << this
				<< " typeid=" << typeid(node).name()
				<< " name=" << node.getName()
				<< std::endl
			;

			// Call Python override if present.
			// Convention:
			//   - None  -> traverse (default)
			//   - True  -> traverse
			//   - False -> prune children
			auto r = call_override<bool>("apply", this, &node);
			auto do_traverse = r.value_or(true);

			if (do_traverse) {
				osg::NodeVisitor::traverse(node);
			}
		}

		// Keep Group overload ONLY to collapse to Node path.
		// No logging, no Python dispatch here.
		void apply(osg::Group& group) override {
			std::cout
				<< "detail::NodeVisitor::apply(Geode&)"
				<< " this=" << this
				<< " typeid=" << typeid(group).name()
				<< " name=" << group.getName()
				<< std::endl
			;

			apply(static_cast<osg::Node&>(group));
		}
	};
}

void bind_NodeVisitor(py::module_& m) {
	auto nv = py::class_<osg::NodeVisitor, detail::NodeVisitor, osg::Object, osg::ref_ptr<osg::NodeVisitor>>(m, "NodeVisitor");

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
		// .def(py::init_alias<>())
		// .def(py::init<>())
		// NodeVisitor(TraversalMode)
		.def(py::init_alias<osg::NodeVisitor::TraversalMode>(), py::arg("traversalMode")=osg::NodeVisitor::TRAVERSE_NONE)
		/* // NodeVisitor(VisitorType, TraversalMode)
		.def(py::init_alias<osg::NodeVisitor::VisitorType, osg::NodeVisitor::TraversalMode>(),
			py::arg("type"),
			py::arg("traversalMode")=osg::NodeVisitor::TRAVERSE_NONE
		) */
		.def("traverse", &osg::NodeVisitor::traverse, py::arg("node"))
		// .def("_traverse", &detail::NodeVisitor::_traverse, py::arg("node"))
		.def("_traverse", [](detail::NodeVisitor* self, osg::Node& node) {
			self->_traverse(node);
		})
		/* .def("apply", [](osg::NodeVisitor* self, osg::Node& node) {
			return self->apply(node);
		}) */
		.def("apply", (void (osg::NodeVisitor::*)(osg::Node&)) &osg::NodeVisitor::apply)
		// .def("apply", (void (osg::NodeVisitor::*)(osg::Group&)) &osg::NodeVisitor::apply)
		.def_property("traversalMask", &osg::NodeVisitor::getTraversalMask, &osg::NodeVisitor::setTraversalMask)
		.def_property("traversalMode", &osg::NodeVisitor::getTraversalMode, &osg::NodeVisitor::setTraversalMode)
	;
}

}
