#include "../osg.hpp"

PYOSG_DISABLE_WARNINGS

#include <osg/ShapeDrawable>

PYOSG_ENABLE_WARNINGS

namespace pyosg {

namespace detail {
	template<>
	void kwargs_init(osg::Sphere& self, const py::kwargs& kwargs) {
	}
}

void bind_Shape(py::module_& m) {
	py::class_<osg::Shape, osg::Object, osg::ref_ptr<osg::Shape>>(m, "Shape");

	py::class_<osg::Sphere, osg::Shape, osg::ref_ptr<osg::Sphere>>(m, "Sphere")
		.def(py::init<>())
		.def(py::init<const osg::Vec3&, float>())
		.def(py::init([](float radius) {
			osg::ref_ptr<osg::Sphere> s = new osg::Sphere(osg::Vec3(), radius);

			// detail::kwargs_init(static_cast<osg::Object&>(*s), kwargs);

			return s;
		}))
		/* .def(py::init([](const osg::Vec3& center, float radius, py::kwargs kwargs) {
			osg::ref_ptr<osg::Sphere> s = new osg::Sphere(center, radius);

			// detail::kwargs_init(static_cast<osg::Object&>(*s), kwargs);

			return s;
		})) */
		.def("__bool__", [](const osg::Sphere* self) {
			return self->valid();
		})
		.def("__repr__", [](const osg::Sphere* self) {
			return py::str("Sphere(center={}, radius={})").format(
				self->getCenter(),
				self->getRadius()
			);
		})
		.def("valid", &osg::Sphere::valid)
#if 0
		.def("accept", [](osg::Node* self, osg::NodeVisitor* nv) {
			self->accept(*nv);
		// }, py::keep_alive<2, 1>())
		})
#endif
		.def_property("center", &osg::Sphere::getCenter, &osg::Sphere::setCenter)
		.def_property("radius", &osg::Sphere::getRadius, &osg::Sphere::setRadius)
	;

	py::class_<osg::Box, osg::Shape, osg::ref_ptr<osg::Box>>(m, "Box")
		.def(py::init<>())
		.def(py::init<const osg::Vec3&, float>())
		.def(py::init<const osg::Vec3&, float, float, float>())
		.def(py::init([](float width) {
			osg::ref_ptr<osg::Box> s = new osg::Box(osg::Vec3(), width);

			return s;
		}))
		.def(py::init([](float x, float y, float z) {
			osg::ref_ptr<osg::Box> s = new osg::Box(osg::Vec3(), x, y, z);

			return s;
		}))
		.def("__bool__", [](const osg::Box* self) {
			return self->valid();
		})
		.def("__repr__", [](const osg::Box* self) {
			return py::str("Sphere(center={}, halfLengths={})").format(
				self->getCenter(),
				self->getHalfLengths()
			);
		})
		.def("valid", &osg::Box::valid)
		.def_property("center", &osg::Box::getCenter, &osg::Box::setCenter)
		.def_property("halfLengths", &osg::Box::getHalfLengths, &osg::Box::setHalfLengths)
		// void setRotation(const Quat& quat) { _rotation = quat; }
		// const Quat&  getRotation() const { return _rotation; }
		// Matrix computeRotationMatrix() const { return Matrix(_rotation); }
		// bool zeroRotation() const { return _rotation.zeroRotation(); }
	;

	// TODO:
	// Cone
	// Cylinder
	// Capsule
	// InfinitePlane
}

}
