#include "../pyosg.hpp"

PYOSG_DISABLE_WARNINGS

#include <osg/Drawable>

PYOSG_ENABLE_WARNINGS

namespace pyosg {

namespace detail {
	template<>
	void kwargs_init(osg::Drawable& self, const py::kwargs& kwargs) {
	}

	class Drawable: public osg::Drawable {
	public:
		void drawImplementation(osg::RenderInfo& ri) const override {
			py::gil_scoped_acquire gil;

			PYBIND11_OVERRIDE(
				void,
				osg::Drawable,
				drawImplementation,
				ri
			);
		}

		osg::BoundingSphere computeBound() const override {
			PYBIND11_OVERRIDE(
				osg::BoundingSphere,
				osg::Drawable,
				computeBound
			);
		}

		osg::BoundingBox computeBoundingBox() const override {
			PYBIND11_OVERRIDE(
				osg::BoundingBox,
				osg::Drawable,
				computeBoundingBox
			);
		}
	};
}

void bind_Drawable(py::module_& m) {
	py::class_<osg::RenderInfo>(m, "RenderInfo")
		.def("getState",
			py::overload_cast<>(&osg::RenderInfo::getState),
			py::return_value_policy::reference
		)
		.def("getView",
			py::overload_cast<>(&osg::RenderInfo::getView),
			py::return_value_policy::reference
		)
		.def_property_readonly("contextID", &osg::RenderInfo::getContextID)
	;

	py::class_<osg::Drawable, osg::Node, detail::Drawable, osg::ref_ptr<osg::Drawable>>(m, "Drawable")
		.def(py::init_alias<>())
		/* .def(py::init([](py::kwargs kwargs) {
			osg::ref_ptr<osg::Drawable> d = new osg::Drawable();

			detail::kwargs_init(*d, kwargs);

			return d;
		})) */
		.def("drawImplementation", [](osg::Drawable& self, osg::RenderInfo& ri) {
			self.drawImplementation(ri);
		})
		.def("computeBound", &osg::Drawable::computeBound)
		.def("computeBoundingBox", &osg::Drawable::computeBoundingBox)
	;
}

}
