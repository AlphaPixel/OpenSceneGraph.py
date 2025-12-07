#include "../pyosg.hpp"

PYOSG_DISABLE_WARNINGS

#include <osg/Group>

PYOSG_ENABLE_WARNINGS

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

#if 0
	struct ChildrenProxy {
		osg::Group* g = nullptr;

		explicit ChildrenProxy(osg::Group* group): g(group) {}

		size_t size() const {
			return g->getNumChildren();
		}

		constexpr auto _index(int index) const {
			auto n = static_cast<int>(g->getNumChildren());

			if(index < 0) index += n;
			if(index < 0 || index >= n) throw py::index_error();

			return static_cast<unsigned int>(index);
		}

		osg::Node* get(int index) const {
			return g->getChild(_index(index));
		}

		void set(int index, osg::Node* n) {
			g->replaceChild(g->getChild(_index(index)), n);
		}

		void del(int index) {
			g->removeChild(_index(index));
		}

		void append(osg::Node* n) {
			// We call the PYTHON METHOD to make sure `keep_alive` is applied.
			py::cast(g).attr("addChild")(n);
		}

		void extend(py::object iterable) {
			for(py::handle item : iterable) {
				// See `append` above.
				py::cast(g).attr("addChild")(item.cast<osg::Node*>());
			}
		}
	};
#endif

	template<>
	struct ContainerTraits<osg::Group> {
		using element_type = osg::Node;

		static size_t size(const osg::Group* g) {
			return g->getNumChildren();
		}

		static element_type* get(osg::Group* g, size_t i) {
			return g->getChild(static_cast<unsigned int>(i));
		}

		static void set(osg::Group* g, size_t i, element_type* n) {
			g->replaceChild(g->getChild(static_cast<unsigned int>(i)), n);
		}

		static void remove(osg::Group* g, size_t i) {
			g->removeChild(static_cast<unsigned int>(i));
		}

		static void append(osg::Group* g, element_type* n) {
			g->addChild(n);
		}

		static constexpr const char* add_method = "addChild";
	};

	using ChildrenProxy = ContainerProxy<osg::Group>;
}

void bind_Group(py::module_& m) {
	auto group = py::class_<osg::Group, osg::Node, osg::ref_ptr<osg::Group>>(m, "Group");

	/* py::class_<detail::ChildrenProxy>(group, "_Children", py::module_local())
		.def("__len__", &detail::ChildrenProxy::size)
		.def("__getitem__", &detail::ChildrenProxy::get)
		.def("__setitem__", &detail::ChildrenProxy::set)
		.def("__delitem__", &detail::ChildrenProxy::del)
		.def("append", &detail::ChildrenProxy::append)
		.def("extend", &detail::ChildrenProxy::extend)
	; */

	detail::ChildrenProxy::bind(group, "_Children");

	group
		.def(py::init<>())
		.def(py::init([](py::args args, py::kwargs kwargs) {
			osg::ref_ptr<osg::Group> g = new osg::Group();

			detail::kwargs_init(*g, kwargs);

			return g;
		}))
		.def("addChild", [](osg::Group& self, osg::Node* child) {
			return self.addChild(child);
		}, py::arg("child"), py::keep_alive<1, 2>())
		.def("getChild",
			static_cast<osg::Node*(osg::Group::*)(unsigned int)>(&osg::Group::getChild),
			py::return_value_policy::reference_internal
		)
		.def("getNumChildren", &osg::Group::getNumChildren)
		.def("removeChild",
			static_cast<bool(osg::Group::*)(osg::Node*)>(&osg::Group::removeChild),
			py::arg("child")
		)
		.def("removeChildren",
			&osg::Group::removeChildren,
			py::arg("index"),
			py::arg("numChildren")
		)
		.def("replaceChild",
			[](osg::Group& self, osg::Node* oldChild, osg::Node* newChild) {
				return self.replaceChild(oldChild, newChild);
			},
			py::arg("oldChild"),
			py::arg("newChild"),
			py::keep_alive<1, 3>()
		)
		.def("addChildren", [](osg::Group& self, const py::args& args) {
			int count = 0;

			for(auto item : args) {
				auto* child = item.cast<osg::Node*>();

				if(self.addChild(child)) count++;
			}

			return count;
		},
		"Add one or more children. Returns number of children added.")
		// This is the more Pythonic way ot interacting with child nodes; people will EXPECT IT.
		// However, it does introduce "identity" errors, since it returns a new instance every call;
		// this means code like the following will fail: `g.children[0] is g.children[0]`, but it's
		// unlikely people will actually check against identity like that. Much more frequently will
		// be checks for EQUALITY (and those will SUCCEED).
		.def_property_readonly("children", [](osg::Group& self) {
			return detail::ChildrenProxy(&self);
		})
	;
}

}
