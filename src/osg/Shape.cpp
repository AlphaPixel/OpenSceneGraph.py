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

	auto th = py::class_<
		osg::TessellationHints,
		osg::Object,
		osg::ref_ptr<osg::TessellationHints>
	>(m, "TessellationHints")
		.def(py::init<>())
	;

	py::enum_<osg::TessellationHints::TessellationMode>(th, "TessellationMode")
		.value("USE_SHAPE_DEFAULTS", osg::TessellationHints::TessellationMode::USE_SHAPE_DEFAULTS)
		.value("USE_TARGET_NUM_FACES", osg::TessellationHints::TessellationMode::USE_TARGET_NUM_FACES)
	;

	th
		.def_property("tessellationMode",
			&osg::TessellationHints::getTessellationMode,
			&osg::TessellationHints::setTessellationMode
		)
		.def_property("detailRatio",
			&osg::TessellationHints::getDetailRatio,
			&osg::TessellationHints::setDetailRatio
		)
		.def_property("targetNumFaces",
			&osg::TessellationHints::getTargetNumFaces,
			&osg::TessellationHints::setTargetNumFaces
		)
		.def_property("createFrontFace",
			&osg::TessellationHints::getCreateFrontFace,
			&osg::TessellationHints::setCreateFrontFace
		)
		.def_property("createBackFace",
			&osg::TessellationHints::getCreateBackFace,
			&osg::TessellationHints::setCreateBackFace
		)
		.def_property("createNormals",
			&osg::TessellationHints::getCreateNormals,
			&osg::TessellationHints::setCreateNormals
		)
		.def_property("createTextureCoords",
			&osg::TessellationHints::getCreateTextureCoords,
			&osg::TessellationHints::setCreateTextureCoords
		)
		.def_property("createTop",
			&osg::TessellationHints::getCreateTop,
			&osg::TessellationHints::setCreateTop
		)
		.def_property("createBottom",
			&osg::TessellationHints::getCreateBottom,
			&osg::TessellationHints::setCreateBottom
		)
		.def_property("createBody",
			&osg::TessellationHints::getCreateBody,
			&osg::TessellationHints::setCreateBody
		)
	;

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
		.def("__bool__", [](const osg::Sphere& self) { return self.valid(); })
		.def("__repr__", [](const osg::Sphere& self) {
			return py::str("Sphere(center={}, radius={})").format(
				self.getCenter(),
				self.getRadius()
			);
		})
		.def("valid", &osg::Sphere::valid)
#if 0
		.def("accept", [](osg::Shape& self, osg::ShapeVisitor* nv) {
			self.accept(*nv);
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
		.def("__bool__", [](const osg::Box& self) {
			return self.valid();
		})
		.def("__repr__", [](const osg::Box& self) {
			return py::str("Box(center={}, halfLengths={})").format(
				self.getCenter(),
				self.getHalfLengths()
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

	py::class_<osg::ShapeDrawable, osg::Geometry, osg::ref_ptr<osg::ShapeDrawable>>(m, "ShapeDrawable")
		.def(py::init<>())
		// NOTE: The following WOULDN'T be safe, because there's no `keep_alive` call.
		// .def(py::init<osg::Shape*, osg::TessellationHints*>())
		.def(py::init([](osg::Shape* shape, osg::TessellationHints* hints) {
			osg::ref_ptr<osg::ShapeDrawable> s = new osg::ShapeDrawable(shape, hints);

			// detail::kwargs_init(static_cast<osg::Object&>(*s), kwargs);

			return s;
		}),
			"shape"_a,
			"hints"_a = nullptr,
			py::keep_alive<1, 2>(),
			py::keep_alive<1, 3>()
		)
		// TODO: I discovered that THIS could be a potential alternative to all the `py::keep_alive`
		// stuff we normally have to deal with; it needs testing and confirmation!
		/* .def(py::init([](
			const osg::ref_ptr<osg::Shape>& shape,
			const osg::ref_ptr<osg::TessellationHints>& hints
		) {
			osg::ref_ptr<osg::ShapeDrawable> s = new osg::ShapeDrawable(shape, hints);

			return s;
		}), "shape"_a, "hints"_a = nullptr) */
		.def("build", &osg::ShapeDrawable::build)
	;
}

}
