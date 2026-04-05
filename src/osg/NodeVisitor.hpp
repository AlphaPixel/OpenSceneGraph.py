#pragma once

#include "callable.hpp"

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
			/* // TODO: Optional logging: keep or delete.
			OSG_INFO
				<< "detail::NodeVisitor::apply(Node&)"
				<< " this=" << this
				<< " typeid=" << typeid(node).name()
				<< " name=" << node.getName()
				<< std::endl
			; */

			// Call Python override if present.
			// Convention:
			//   - None  -> traverse (default)
			//   - True  -> traverse
			//   - False -> prune children
			auto r = call_override<bool>("apply", this, &node);

			if(r.value_or(true)) osg::NodeVisitor::traverse(node);
		}

		// Keep Group overload ONLY to collapse to Node path.
		// No logging, no Python dispatch here.
		void apply(osg::Group& group) override {
			/* OSG_INFO
				<< "detail::NodeVisitor::apply(Geode&)"
				<< " this=" << this
				<< " typeid=" << typeid(group).name()
				<< " name=" << group.getName()
				<< std::endl
			; */

			apply(static_cast<osg::Node&>(group));
		}
	};
}

void bind_NodeVisitor(py::module_& m);

}
