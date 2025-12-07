#include "../pyosg.hpp"

PYOSG_DISABLE_WARNINGS

#include <osg/Geode>

PYOSG_ENABLE_WARNINGS

namespace pyosg {

namespace detail {
	template<>
	void kwargs_init(osg::Geode& self, const py::kwargs& kwargs) {
		kwargs_init(static_cast<osg::Group&>(self), kwargs);

		if(kwargs.contains("drawables")) {
			for(py::handle child : kwargs["drawables"]) {
				self.addDrawable(child.cast<osg::Drawable*>());
			}
		}
	}

	template<>
	struct ContainerTraits<osg::Geode> {
		using element_type = osg::Drawable;

		static size_t size(const osg::Geode* g) {
			return g->getNumDrawables();
		}

		static element_type* get(osg::Geode* g, size_t i) {
			return g->getDrawable(static_cast<unsigned int>(i));
		}

		static void set(osg::Geode* g, size_t i, element_type* d) {
			g->replaceDrawable(g->getDrawable(static_cast<unsigned int>(i)), d);
		}

		static void remove(osg::Geode* g, size_t i) {
			g->removeDrawables(static_cast<unsigned int>(i));
		}

		static void append(osg::Geode* g, element_type* d) {
			g->addDrawable(d);
		}

		static constexpr const char* add_method = "addDrawable";
	};

	using DrawablesProxy = ContainerProxy<osg::Geode>;
}

void bind_Geode(py::module_& m) {
	auto geode = py::class_<osg::Geode, osg::Group, osg::ref_ptr<osg::Geode>>(m, "Geode");

	detail::DrawablesProxy::bind(geode, "_Drawables");

	geode
		.def(py::init<>())
		.def(py::init([](py::args args, py::kwargs kwargs) {
			osg::ref_ptr<osg::Geode> g = new osg::Geode();

			detail::kwargs_init(*g, kwargs);

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
		"Add one or more children. Returns number of children added.") */
		.def_property_readonly("drawables", [](osg::Geode& self) {
			return detail::DrawablesProxy(&self);
		})
	;
}

}
