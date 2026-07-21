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
	auto group = py::class_<osg::Group, osg::Node, osg::ref_ptr<osg::Group>>(m, "Group");

	pyx::bind_proxy_property<detail::ChildrenProxy, osg::Group, detail::ChildrenStorage>(
		group, "_Children", "children"
	);

	group
		.def(py::init<>())
		.def(py::init(pyx::kwargs_ctor<osg::Group>()))

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
		})
	;
}

}
