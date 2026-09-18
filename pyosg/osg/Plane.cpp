#include "Plane.hpp"

namespace pyosg {

using value_type = osg::Plane::value_type;
using Vec3_type = osg::Plane::Vec3_type;

void bind_Plane(py::module_& m) {
	auto plane = py::class_<osg::Plane>(
		m,
		"Plane",
		"An infinite plane, described by the implicit equation a*x+b*y+c*z+d=0; used for "
		"frustum culling, clip planes, and other half-space tests."
	)
		.def(py::init<>(), "Create a zero-initialized (mathematically invalid) plane.")
		.def(py::init<const osg::Plane&>(), "Create a copy of another plane.")
		.def(py::init<value_type, value_type, value_type, value_type>(),
			"Create a plane from its a, b, c, d coefficients."
		)
		.def(py::init<const osg::Vec4f&>(),
			"Create a plane from a Vec4 [a,b,c,d]."
		)
		.def(py::init<const osg::Vec4d&>(),
			"Create a plane from a Vec4 [a,b,c,d]."
		)
		.def(py::init<const Vec3_type&, value_type>(),
			"Create a plane from a normal and the negative distance from the origin."
		)
		.def(py::init<const Vec3_type&, const Vec3_type&, const Vec3_type&>(),
			"Create a plane through three points, normal from (v2-v1)^(v3-v2)."
		)
		.def(py::init<const Vec3_type&, const Vec3_type&>(),
			"Create a plane from a normal and a point that lies on it."
		)

		.def(py::self == py::self)
		.def(py::self != py::self)

		.def("set", py::overload_cast<const osg::Plane&>(&osg::Plane::set),
			"Set this plane to a copy of another plane."
		)
		.def("set", py::overload_cast<value_type, value_type, value_type, value_type>(&osg::Plane::set),
			"Set this plane from its a, b, c, d coefficients."
		)
		.def("set", py::overload_cast<const osg::Vec4f&>(&osg::Plane::set),
			"Set this plane from a Vec4 [a,b,c,d]."
		)
		.def("set", py::overload_cast<const osg::Vec4d&>(&osg::Plane::set),
			"Set this plane from a Vec4 [a,b,c,d]."
		)
		.def("set", py::overload_cast<const Vec3_type&, double>(&osg::Plane::set),
			"Set this plane from a normal and the negative distance from the origin."
		)
		.def("set", py::overload_cast<
			const Vec3_type&,
			const Vec3_type&,
			const Vec3_type&
		>(&osg::Plane::set),
			"Set this plane through three points, normal from (v2-v1)^(v3-v2)."
		)
		.def("set", py::overload_cast<const Vec3_type&, const Vec3_type&>(&osg::Plane::set),
			"Set this plane from a normal and a point that lies on it."
		)

		.def("flip", &osg::Plane::flip, "Reverse the plane's orientation in place (negate a, b, c, d).")
		.def("makeUnitLength", &osg::Plane::makeUnitLength,
			"Scale this plane's coefficients in place so a^2+b^2+c^2 = 1."
		)
		.def("valid", &osg::Plane::valid,
			"Return whether every coefficient is a valid number (does NOT check the normal is non-zero)."
		)
		.def("isNaN", &osg::Plane::isNaN, "Return whether any coefficient is NaN.")

		.def_property_readonly("normal", &osg::Plane::getNormal, "The plane's normal (a, b, c).")
		.def("asVec4", &osg::Plane::asVec4, "Return the plane's coefficients as a Vec4.")

		.def("distance", py::overload_cast<const osg::Vec3f&>(&osg::Plane::distance, py::const_),
			"Return the signed distance from a point to the plane (requires makeUnitLength() first)."
		)
		.def("distance", py::overload_cast<const osg::Vec3d&>(&osg::Plane::distance, py::const_),
			"Return the signed distance from a point to the plane (requires makeUnitLength() first)."
		)
		.def("dotProductNormal", py::overload_cast<const osg::Vec3f&>(&osg::Plane::dotProductNormal, py::const_),
			"Return the dot product of the plane's normal and a point."
		)
		.def("dotProductNormal", py::overload_cast<const osg::Vec3d&>(&osg::Plane::dotProductNormal, py::const_),
			"Return the dot product of the plane's normal and a point."
		)

		.def("intersect",
			py::overload_cast<const std::vector<osg::Vec3f>&>(&osg::Plane::intersect, py::const_),
			"Return 1 if every point is above the plane, -1 if every point is below, 0 if mixed."
		)
		.def("intersect",
			py::overload_cast<const std::vector<osg::Vec3d>&>(&osg::Plane::intersect, py::const_),
			"Return 1 if every point is above the plane, -1 if every point is below, 0 if mixed."
		)
		.def("intersect",
			py::overload_cast<const osg::BoundingSphere&>(&osg::Plane::intersect, py::const_),
			"Return 1 if the sphere is entirely above the plane, -1 entirely below, 0 if it straddles it."
		)
		.def("intersect",
			py::overload_cast<const osg::BoundingBox&>(&osg::Plane::intersect, py::const_),
			"Return 1 if the box is entirely above the plane, -1 entirely below, 0 if it straddles it."
		)

		.def("transform", &osg::Plane::transform,
			"Transform the plane in place by a matrix (inverts the matrix internally; "
			"prefer transformProvidingInverse() if the inverse is already known)."
		)
		.def("transformProvidingInverse", &osg::Plane::transformProvidingInverse,
			"Transform the plane in place by a matrix, given its already-computed inverse."
		)

		.def("__len__", [](const osg::Plane&){ return 4; },
			"Return the number of coefficients, always 4."
		)

		.def("__iter__", [](const osg::Plane& p){
			py::tuple t(4);

			OSGX_DISABLE_WARNINGS

				for(size_t i = 0; i < 4; i++) t[i] = p[i];

			OSGX_ENABLE_WARNINGS

			return py::iter(t);
		}, "Iterate over the plane's a, b, c, d coefficients in order.")

		.def("__repr__", [](const osg::Plane& p) {
			return detail::seq_repr<4>("Plane", [&](size_t i) {
				OSGX_DISABLE_WARNINGS

					return p[i];

				OSGX_ENABLE_WARNINGS
			});
		}, "Return a constructor-style representation of this plane.")
	;

	OSGX_DISABLE_WARNINGS

		plane
			.def("__getitem__", [](const osg::Plane& p, py::ssize_t i) {
				return p[detail::n_index(4, i)];
			}, "Return the coefficient at index (negative indices count from the end).")

			.def("__setitem__", [](osg::Plane& p, py::ssize_t i, value_type val){
				p[detail::n_index(4, i)] = val;
			}, "Set the coefficient at index (negative indices count from the end).")
		;

	OSGX_ENABLE_WARNINGS
}

}
