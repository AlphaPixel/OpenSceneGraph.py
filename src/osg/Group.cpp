// #include "../pyosg.hpp"
#include "lifetime-probe.hpp"

PYOSG_DISABLE_WARNINGS

#include <osg/Group>

PYOSG_ENABLE_WARNINGS

#include "pybind11x.hpp"

namespace pyx = pybind11x;

template<>
struct pyx::SequenceTraits<osg::Group> {
	using element_type = osg::Node;
	using value_type = element_type*;

	static value_type from_python(py::handle h) {
		return h.cast<value_type>();
	}

	static size_t size(const osg::Group* g) {
		return g->getNumChildren();
	}

	static element_type* get(osg::Group* g, size_t i) {
		return g->getChild(static_cast<unsigned int>(i));
	}

	static void set(osg::Group* g, size_t i, value_type n) {
		g->replaceChild(g->getChild(static_cast<unsigned int>(i)), n);
	}

	static void del(osg::Group* g, size_t i) {
		g->removeChild(static_cast<unsigned int>(i));
	}

	static void append(osg::Group* g, value_type n) {
		g->addChild(n);
	}
};

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

	using ChildrenProxy = pyx::SequenceProxy<osg::Group>;
	using ChildrenStorage = pyx::ProxyStorageOSG<osg::Group, ChildrenProxy>;
}

void bind_Group(py::module_& m) {
	auto group = py::class_<osg::Group, osg::Node, osg::ref_ptr<osg::Group>>(m, "Group");

	detail::ChildrenProxy::bind(group, "_Children");

	group
		.def(py::init<>())
		.def(py::init([](py::args args, py::kwargs kwargs) {
			osg::ref_ptr<osg::Group> g = new osg::Group();

			detail::kwargs_init(*g, kwargs);

			return g;
		}))
		.def_property_readonly("children", [](osg::Group& self) -> detail::ChildrenProxy& {
			return detail::ChildrenStorage::get(self)->template proxy<detail::ChildrenProxy>();
		}, py::return_value_policy::reference_internal)

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
