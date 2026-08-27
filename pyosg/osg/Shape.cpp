#include "../pyosg.hpp"

OSGX_DISABLE_WARNINGS

#include <osg/ShapeDrawable>

OSGX_ENABLE_WARNINGS

namespace pyosg {

void bind_Shape(py::module_& m) {
	py::class_<osg::Shape, osg::Object, osg::ref_ptr<osg::Shape>>(
		m,
		"Shape",
		"Base class for procedural geometric primitives (Sphere, Box, etc.) that a "
		"ShapeDrawable can tessellate and render."
	);

	auto th = py::class_<
		osg::TessellationHints,
		osg::Object,
		osg::ref_ptr<osg::TessellationHints>
	>(
		m,
		"TessellationHints",
		"Controls the level of detail and which faces ShapeDrawable.build() generates for "
		"a Shape."
	)
		.def(py::init<>(), "Create tessellation hints with OSG's default settings.")
	;

	py::enum_<osg::TessellationHints::TessellationMode>(
		th,
		"TessellationMode",
		"Choose whether ShapeDrawable follows a shape's defaults or targets a face count."
	)
		.value("USE_SHAPE_DEFAULTS", osg::TessellationHints::TessellationMode::USE_SHAPE_DEFAULTS)
		.value("USE_TARGET_NUM_FACES", osg::TessellationHints::TessellationMode::USE_TARGET_NUM_FACES)
		.export_values()
	;

	th
		.def_property("tessellationMode",
			&osg::TessellationHints::getTessellationMode,
			&osg::TessellationHints::setTessellationMode,
			"Whether to use the shape's defaults or target a number of faces."
		)
		.def_property("detailRatio",
			&osg::TessellationHints::getDetailRatio,
			&osg::TessellationHints::setDetailRatio,
			"Multiplier controlling the tessellation detail level."
		)
		.def_property("targetNumFaces",
			&osg::TessellationHints::getTargetNumFaces,
			&osg::TessellationHints::setTargetNumFaces,
			"Requested face count when tessellationMode is USE_TARGET_NUM_FACES."
		)
		.def_property("createFrontFace",
			&osg::TessellationHints::getCreateFrontFace,
			&osg::TessellationHints::setCreateFrontFace,
			"Whether tessellation generates front-facing geometry."
		)
		.def_property("createBackFace",
			&osg::TessellationHints::getCreateBackFace,
			&osg::TessellationHints::setCreateBackFace,
			"Whether tessellation generates back-facing geometry."
		)
		.def_property("createNormals",
			&osg::TessellationHints::getCreateNormals,
			&osg::TessellationHints::setCreateNormals,
			"Whether tessellation generates normal vectors."
		)
		.def_property("createTextureCoords",
			&osg::TessellationHints::getCreateTextureCoords,
			&osg::TessellationHints::setCreateTextureCoords,
			"Whether tessellation generates texture coordinates."
		)
		.def_property("createTop",
			&osg::TessellationHints::getCreateTop,
			&osg::TessellationHints::setCreateTop,
			"Whether tessellation generates top caps where applicable."
		)
		.def_property("createBottom",
			&osg::TessellationHints::getCreateBottom,
			&osg::TessellationHints::setCreateBottom,
			"Whether tessellation generates bottom caps where applicable."
		)
		.def_property("createBody",
			&osg::TessellationHints::getCreateBody,
			&osg::TessellationHints::setCreateBody,
			"Whether tessellation generates the shape's body."
		)
	;

	py::class_<osg::Sphere, osg::Shape, osg::ref_ptr<osg::Sphere>>(
		m,
		"Sphere",
		"A Shape describing a sphere by center and radius."
	)
		.def(py::init<>(), "Create a unit sphere centered at the origin.")
		.def(py::init<const osg::Vec3&, float>(), "Create a sphere from its center and radius.")
		.def(py::init([](float radius) {
			osg::ref_ptr<osg::Sphere> s = new osg::Sphere(osg::Vec3(), radius);

			// detail::kwargs_init(static_cast<osg::Object&>(*s), kwargs);

			return s;
		}), "Create a sphere with the given radius centered at the origin.")
		/* .def(py::init([](const osg::Vec3& center, float radius, py::kwargs kwargs) {
			osg::ref_ptr<osg::Sphere> s = new osg::Sphere(center, radius);

			// detail::kwargs_init(static_cast<osg::Object&>(*s), kwargs);

			return s;
		})) */
		.def("__bool__", [](const osg::Sphere& self) { return self.valid(); },
			"Return whether the sphere has a non-negative radius."
		)
		.def("__repr__", [](const osg::Sphere& self) {
			return py::str("Sphere(center={}, radius={})").format(
				self.getCenter(),
				self.getRadius()
			);
		}, "Return a constructor-style representation of this sphere.")
		.def("valid", &osg::Sphere::valid,
			"Return whether the sphere has a non-negative radius."
		)
#if 0
		.def("accept", [](osg::Shape& self, osg::ShapeVisitor* nv) {
			self.accept(*nv);
		// }, py::keep_alive<2, 1>())
		})
#endif
		.def_property("center", &osg::Sphere::getCenter, &osg::Sphere::setCenter,
			"The sphere's center."
		)
		.def_property("radius", &osg::Sphere::getRadius, &osg::Sphere::setRadius,
			"The sphere's radius."
		)
	;

	py::class_<osg::Box, osg::Shape, osg::ref_ptr<osg::Box>>(
		m,
		"Box",
		"A Shape describing an axis-aligned box by center and half-lengths."
	)
		.def(py::init<>(),
			"Create a unit box centered at the origin."
		)
		.def(py::init<const osg::Vec3&, float>(),
			"Create a cubic box from its center and edge length."
		)
		.def(py::init<const osg::Vec3&, float, float, float>(),
			"Create a box from its center and x, y, z edge lengths."
		)
		.def(py::init([](float width) {
			osg::ref_ptr<osg::Box> s = new osg::Box(osg::Vec3(), width);

			return s;
		}), "Create a cubic box with the given edge length centered at the origin.")
		.def(py::init([](float x, float y, float z) {
			osg::ref_ptr<osg::Box> s = new osg::Box(osg::Vec3(), x, y, z);

			return s;
		}), "Create a box with the given x, y, z edge lengths centered at the origin.")
		.def("__bool__", [](const osg::Box& self) {
			return self.valid();
		}, "Return whether the box's x half-length is non-negative.")
		.def("__repr__", [](const osg::Box& self) {
			return py::str("Box(center={}, halfLengths={})").format(
				self.getCenter(),
				self.getHalfLengths()
			);
		}, "Return a constructor-style representation of this box.")
		.def("valid", &osg::Box::valid, "Return whether the box's x half-length is non-negative.")
		.def_property("center", &osg::Box::getCenter, &osg::Box::setCenter, "The box's center.")
		.def_property("halfLengths", &osg::Box::getHalfLengths, &osg::Box::setHalfLengths,
			"The distances from the center to each pair of faces."
		)
		// void setRotation(const Quat& quat) { _rotation = quat; }
		// const Quat& getRotation() const { return _rotation; }
		// Matrix computeRotationMatrix() const { return Matrix(_rotation); }
		// bool zeroRotation() const { return _rotation.zeroRotation(); }
	;

	// TODO:
	// Cone
	// Cylinder
	// Capsule
	// InfinitePlane

	py::class_<osg::ShapeDrawable, osg::Geometry, osg::ref_ptr<osg::ShapeDrawable>>(
		m,
		"ShapeDrawable",
		"A Drawable that tessellates a Shape (per its TessellationHints) into renderable "
		"geometry with a flat color."
	)
		.def(py::init<>(), "Create an empty shape drawable.")
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
			py::keep_alive<1, 3>(),
			"Create a drawable for shape, optionally using tessellation hints."
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
		.def("build", &osg::ShapeDrawable::build,
			"Rebuild the drawable geometry from its shape and tessellation hints."
		)
		.def_property(
			"color",
			&osg::ShapeDrawable::getColor,
			&osg::ShapeDrawable::setColor,
			"The shape's flat color."
		)
	;
}

}
