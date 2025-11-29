#include "../osg.hpp"

PYOSG_DISABLE_WARNINGS

#include <osg/Geode>

PYOSG_ENABLE_WARNINGS

namespace pyosg {

namespace detail {
	/* template<>
	void kwargs_init(osg::Geode& self, const py::kwargs& kwargs) {
		kwargs_init(static_cast<osg::Node&>(self), kwargs);

		if(kwargs.contains("children")) {
			for(py::handle child : kwargs["children"]) {
				self.addChild(child.cast<osg::Node*>());
			}
		}
	}

	struct ChildrenProxy {
		osg::Geode* g = nullptr;

		explicit ChildrenProxy(osg::Geode* group): g(group) {}

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
	}; */
}

void bind_Geode(py::module_& m) {
	auto geode = py::class_<osg::Geode, osg::Group, osg::ref_ptr<osg::Geode>>(m, "Geode");

	/* py::class_<detail::ChildrenProxy>(group, "_Children", py::module_local())
		.def("__len__", &detail::ChildrenProxy::size)
		.def("__getitem__", &detail::ChildrenProxy::get)
		.def("__setitem__", &detail::ChildrenProxy::set)
		.def("__delitem__", &detail::ChildrenProxy::del)
		.def("append", &detail::ChildrenProxy::append)
		.def("extend", &detail::ChildrenProxy::extend)
	; */

	geode
		.def(py::init<>())
		.def(py::init([](py::args args, py::kwargs kwargs) {
			osg::ref_ptr<osg::Geode> g = new osg::Geode();

			// detail::kwargs_init(*g, kwargs);

			return g;
		}))
		.def("addDrawable", [](osg::Geode& self, osg::Drawable* drawable) {
			return self.addDrawable(drawable);
		}, py::arg("drawable"), py::keep_alive<1, 2>())
		/* .def("getChild",
			static_cast<osg::Node*(osg::Geode::*)(unsigned int)>(&osg::Geode::getChild),
			py::return_value_policy::reference_internal
		)
		.def("getNumChildren", &osg::Geode::getNumChildren)
		.def("removeChild",
			static_cast<bool(osg::Geode::*)(osg::Node*)>(&osg::Geode::removeChild),
			py::arg("child")
		)
		.def("removeChildren",
			&osg::Geode::removeChildren,
			py::arg("index"),
			py::arg("numChildren")
		)
		.def("replaceChild",
			[](osg::Geode& self, osg::Node* oldChild, osg::Node* newChild) {
				return self.replaceChild(oldChild, newChild);
			},
			py::arg("oldChild"),
			py::arg("newChild"),
			py::keep_alive<1, 3>()
		)
		.def("addChildren", [](osg::Geode& self, const py::args& args) {
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
		.def_property_readonly("children", [](osg::Geode& self) {
			return detail::ChildrenProxy(&self);
		}) */
	;
}

}
