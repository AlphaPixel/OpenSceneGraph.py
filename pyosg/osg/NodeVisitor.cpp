#include "NodeVisitor.hpp"

namespace pyosg {

void bind_NodeVisitor(py::module_& m) {
	// TODO: This _works_, but isn't really what we WANT; it'll return the pointers, exactly as
	// requested, but it doesn't do us much good in Python, unless we're just passing it directly
	// to something else (like the `osg::computeWorldToLocal` helpers).
	// py::bind_vector<std::vector<osg::Node*>>(m, "NodePath");

	// TODO: This is a readonly variant I'm testing!
	py::class_<osg::NodePath>(
		m,
		"NodePath",
		"An ordered sequence of Nodes from the scene graph root down to a specific node, as "
		"returned by NodeVisitor.nodePath."
	)
		.def("__len__", [](const osg::NodePath& self) {
			return self.size();
		}, "Return the number of nodes in the path.")
		.def("__repr__", [](const osg::NodePath& self) {
			std::ostringstream out;

			out << "NodePath[";

			for(std::size_t i = 0; i < self.size(); ++i) {
				if(i) { out << ", "; }

				out << self[i];
			}

			out << "]";

			return out.str();
		}, "Return each node's memory address as a bracketed, comma-separated list.")
	;

	auto nv = py::class_<
		osg::NodeVisitor,
		detail::NodeVisitor,
		osg::Object,
		osg::ref_ptr<osg::NodeVisitor>
	>(
		m,
		"NodeVisitor",
		"Base class for traversing the scene graph and applying custom logic to Nodes it visits."
	);

	py::enum_<osg::NodeVisitor::TraversalMode>(
		nv,
		"TraversalMode",
		"How traverse() moves through the graph by default: not at all, up to parents, down "
		"to every child, or down to only the active children (LOD/Switch-selected)."
	)
		.value("TRAVERSE_NONE", osg::NodeVisitor::TRAVERSE_NONE)
		.value("TRAVERSE_PARENTS", osg::NodeVisitor::TRAVERSE_PARENTS)
		.value("TRAVERSE_ALL_CHILDREN", osg::NodeVisitor::TRAVERSE_ALL_CHILDREN)
		.value("TRAVERSE_ACTIVE_CHILDREN", osg::NodeVisitor::TRAVERSE_ACTIVE_CHILDREN)
		.export_values()
	;

	py::enum_<osg::NodeVisitor::VisitorType>(
		nv,
		"VisitorType",
		"Which built-in traversal role this visitor plays (update/event/cull/intersection/"
		"etc.) - lets Nodes and StateSets special-case behavior per traversal type."
	)
		.value("NODE_VISITOR", osg::NodeVisitor::NODE_VISITOR)
		.value("UPDATE_VISITOR", osg::NodeVisitor::UPDATE_VISITOR)
		.value("EVENT_VISITOR", osg::NodeVisitor::EVENT_VISITOR)
		.value("COLLECT_OCCLUDER_VISITOR", osg::NodeVisitor::COLLECT_OCCLUDER_VISITOR)
		.value("CULL_VISITOR", osg::NodeVisitor::CULL_VISITOR)
		.value("INTERSECTION_VISITOR", osg::NodeVisitor::INTERSECTION_VISITOR)
		.export_values()
	;

	nv
		.def(
			py::init_alias<osg::NodeVisitor::TraversalMode>(),
			"Create a NodeVisitor with the given default traversal mode; subclass and "
			"override apply(node) to act on visited nodes.",
			"traversalMode"_a=osg::NodeVisitor::TRAVERSE_NONE
		)
		.def("traverse", &osg::NodeVisitor::traverse,
			"Continue the traversal from node according to traversalMode - call from "
			"within an apply() override to visit children/parents."
			, "node"_a)
		.def("_traverse", [](detail::NodeVisitor& self, osg::Node& node) {
			self._traverse(node);
		}, "Invoke the base class's default traverse() behavior, bypassing any Python override.")
		.def("apply", py::overload_cast<osg::Node&>(&osg::NodeVisitor::apply),
			"Visit a single Node; the default implementation calls traverse(node), so a "
			"Python override should call self.traverse(node) to keep descending."
		)
		.def("reset", &osg::NodeVisitor::reset,
			"Reset per-traversal state to prepare this visitor for reuse on another traversal."
		)
		.def_property(
			"traversalMask",
			&osg::NodeVisitor::getTraversalMask,
			&osg::NodeVisitor::setTraversalMask,
			"Bitmask ANDed against each visited Node's nodeMask; a zero result skips that "
			"node's subgraph."
		)
		.def_property(
			"traversalNumber",
			&osg::NodeVisitor::getTraversalNumber,
			&osg::NodeVisitor::setTraversalNumber,
			"Frame-scoped counter used to detect whether a node has already been visited "
			"this traversal (e.g. for DAG nodes with multiple parents)."
		)
		.def_property(
			"traversalMode",
			&osg::NodeVisitor::getTraversalMode,
			&osg::NodeVisitor::setTraversalMode,
			"Which nodes traverse() visits by default; see TraversalMode."
		)
		.def_property(
			"frameStamp",
			py::overload_cast<>(&osg::NodeVisitor::getFrameStamp, py::const_),
			&osg::NodeVisitor::setFrameStamp,
			py::return_value_policy::reference,
			"The FrameStamp (frame number, simulation time) this traversal is running under."
		)
		// TODO: See the comment for `bind_vector` above!
		.def_property_readonly(
			"nodePath",
			py::overload_cast<>(&osg::NodeVisitor::getNodePath, py::const_),
			py::return_value_policy::reference_internal,
			"The NodePath from the traversal's root down to the node currently being visited."
		)
	;
}

}
