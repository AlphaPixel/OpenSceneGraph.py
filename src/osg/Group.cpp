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

	template<>
	struct SequenceTraits<osg::Group> {
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

	using ChildrenProxy = SequenceProxy<osg::Group>;
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
		}, py::keep_alive<1, 2>())
		.def("getChild",
			py::overload_cast<unsigned int>(&osg::Group::getChild),
			py::return_value_policy::reference_internal
		)
		.def("getNumChildren", &osg::Group::getNumChildren)
		.def("removeChild",
			// TODO: No `py::overload_cast`?
			 static_cast<bool(osg::Group::*)(osg::Node*)>(&osg::Group::removeChild)
			// py::overload_cast<osg::Node*>(&osg::Group::removeChild)
		)
		.def("removeChildren", &osg::Group::removeChildren)
		.def("replaceChild",
			[](osg::Group& self, osg::Node* oldChild, osg::Node* newChild) {
				return self.replaceChild(oldChild, newChild);
			},
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
