#include "Group.hpp"

namespace pybind11x {
	template<>
	void kwargs_init_own(osg::Group& self, const py::kwargs& kwargs) {
		if(kwargs.contains("children")) {
			for(py::handle child : kwargs["children"]) {
				self.addChild(child.cast<osg::Node*>());
			}
		}
	}
}

namespace pyosg {

void bind_Group(py::module_& m) {
	auto group = py::class_<osg::Group, osg::Node, osg::ref_ptr<osg::Group>>(
		m,
		"Group",
		"A node that owns an ordered list of child Nodes, forming the branches of the scene "
		"graph. Children are exposed via the .children sequence proxy (indexing, iteration, "
		"append/insert/remove) rather than addChild()/removeChild()/getChild()."
	);

	pyx::bind_proxy_property<detail::ChildrenProxy, osg::Group, detail::ChildrenStorage>(
		group, "_Children", "children",
		"Sequence proxy over this Group's child Nodes (indexing, iteration, append/extend)."
	);

	group
		.def(py::init<>(), "Create a Group with no children.")
		.def(
			py::init(pyx::kwargs_ctor<osg::Group>()),
			"Create a Group, optionally populating .children from a children= sequence of Nodes."
		)

		.def_static("test_cpp", []() {
			auto* g = new osg::Group();

			g->setName("g");

			// n->setUpdateCallback(new detail::TestCallback());
			detail::LifetimeProbe::attachTo(g);

			auto addNode = [&g](const std::string& name) {
				auto* n = new osg::Node();

				n->setName(name);

				detail::LifetimeProbe::attachTo(n);

				g->addChild(n);
			};

			addNode("n0");
			addNode("n1");
			addNode("n2");

			return g;
		}, "Internal C++-side lifetime probe: build a Group with 3 named, tracked child Nodes "
			"for testing ref_ptr/identity lifecycle behavior, not for general use."
		)
	;
}

}
