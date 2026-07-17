#include "Group.hpp"

namespace pyosg {

namespace detail {
	template<>
	void kwargs_init(osg::Group& self, const py::kwargs& kwargs) {
		kwargs_init(static_cast<osg::Node&>(self), kwargs);

		if(kwargs.contains("children")) {
			for(py::handle child : kwargs["children"]) {
				self.addChild(child.cast<osg::Node*>());
			}
		}
	}
}

void bind_Group(py::module_& m) {
	auto group = py::class_<osg::Group, osg::Node, osg::ref_ptr<osg::Group>>(m, "Group");

	pyx::bind_proxy_property<detail::ChildrenProxy, osg::Group, detail::ChildrenStorage>(
		group, "_Children", "children"
	);

	group
		.def(py::init<>())
		.def(py::init([](py::args args, py::kwargs kwargs) {
			osg::ref_ptr<osg::Group> g = new osg::Group();

			detail::kwargs_init(*g, kwargs);

			return g;
		}))

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
