#pragma once

#include "../pyosg.hpp"

OSGX_DISABLE_WARNINGS

#include <osg/BoundingBox>
#include <osg/BoundingSphere>

OSGX_ENABLE_WARNINGS

namespace pyosg {

namespace detail {
	template<typename T>
	auto bind_BoundingBox(py::module_& m, const char* name) {
		using vec_type = typename T::vec_type;
		using value_type = typename T::value_type;

		return py::class_<T>(
			m,
			name,
			"An axis-aligned box, expressed as [xMin,xMax]x[yMin,yMax]x[zMin,zMax]; used for "
			"fast bounds/culling tests before falling back to real geometry intersection."
		)
			.def(py::init<>(), "Create an invalid (empty) box; expandBy() makes it valid.")
			.def(py::init<const T&>(), "Create a copy of another box.")
			.def(py::init<
				value_type, value_type, value_type,
				value_type, value_type, value_type
			>(), "Create a box from explicit xMin, yMin, zMin, xMax, yMax, zMax.")
			.def(py::init<const vec_type&, const vec_type&>(),
				"Create a box spanning two corner points."
			)
			.def(py::self == py::self)
			.def(py::self != py::self)
			.def("valid", &T::valid, "Return whether this box has been expanded to cover any point.")
			.def_property("xMin",
				py::overload_cast<>(&T::xMin, py::const_),
				[](T& self, value_type v) { self.xMin() = v; },
				"The box's minimum X extent."
			)
			.def_property("xMax",
				py::overload_cast<>(&T::xMax, py::const_),
				[](T& self, value_type v) { self.xMax() = v; },
				"The box's maximum X extent."
			)
			.def_property("yMin",
				py::overload_cast<>(&T::yMin, py::const_),
				[](T& self, value_type v) { self.yMin() = v; },
				"The box's minimum Y extent."
			)
			.def_property("yMax",
				py::overload_cast<>(&T::yMax, py::const_),
				[](T& self, value_type v) { self.yMax() = v; },
				"The box's maximum Y extent."
			)
			.def_property("zMin",
				py::overload_cast<>(&T::zMin, py::const_),
				[](T& self, value_type v) { self.zMin() = v; },
				"The box's minimum Z extent."
			)
			.def_property("zMax",
				py::overload_cast<>(&T::zMax, py::const_),
				[](T& self, value_type v) { self.zMax() = v; },
				"The box's maximum Z extent."
			)
			.def_property_readonly("center", &T::center, "The midpoint of the box.")
			.def_property_readonly("radius", &T::radius,
				"The radius of the smallest sphere, centered on `center`, that contains the box."
			)
			.def_property_readonly("radius2", &T::radius2, "The square of `radius`.")
			.def("corner", &T::corner,
				"Return one of the box's 8 corner points, indexed 0-7 by which extreme "
				"(min/max) each axis takes (bit 0=x, bit 1=y, bit 2=z)."
			)
			.def("expandBy", static_cast<void(T::*)(const vec_type&)>(&T::expandBy),
				"Grow the box in place to also contain a point."
			)
			.def("expandBy", static_cast<void(T::*)(const T&)>(&T::expandBy),
				"Grow the box in place to also contain another box."
			)
			.def("expandBy", static_cast<void(T::*)(const osg::BoundingSphere&)>(&T::expandBy),
				"Grow the box in place to also contain a sphere."
			)
			.def("intersect", &T::intersect,
				"Return the box formed by the overlap of this box and another."
			)
			.def("intersects", &T::intersects, "Return whether this box overlaps another.")
			.def("contains", py::overload_cast<const vec_type&>(&T::contains, py::const_),
				"Return whether a point lies within the box."
			)
			.def("contains", py::overload_cast<const vec_type&, value_type>(&T::contains, py::const_),
				"Return whether a point lies within the box, expanded outward by a margin."
			)
		;
	}

	template<typename T>
	auto bind_BoundingSphere(py::module_& m, const char* name) {
		using vec_type = typename T::vec_type;
		using value_type = typename T::value_type;

		return py::class_<T>(
			m,
			name,
			"A bounding sphere (center + radius); cheaper to test than a BoundingBox, used as "
			"OSG's primary node-bounds representation for culling."
		)
			.def(py::init<>(), "Create an invalid (empty) sphere; expandBy() makes it valid.")
			.def(py::init<const T&>(), "Create a copy of another sphere.")
			.def(py::init<const vec_type&, value_type>(), "Create a sphere from a center and radius.")
			.def(py::self == py::self)
			.def(py::self != py::self)
			.def("valid", &T::valid, "Return whether this sphere has been expanded to cover any point.")
			.def_property("center",
				py::overload_cast<>(&T::center, py::const_),
				[](T& self, vec_type v) { self.center() = v; },
				"The sphere's center point."
			)
			.def_property("radius",
				py::overload_cast<>(&T::radius, py::const_),
				[](T& self, value_type v) { self.radius() = v; },
				"The sphere's radius."
			)
			.def_property_readonly("radius2", &T::radius2, "The square of `radius`.")
			.def("expandBy", static_cast<void(T::*)(const vec_type&)>(&T::expandBy),
				"Grow the sphere in place to also contain a point."
			)
			.def("expandBy", static_cast<void(T::*)(const T&)>(&T::expandBy),
				"Grow the sphere in place to also contain another sphere."
			)
			.def("expandBy", static_cast<void(T::*)(const osg::BoundingBox&)>(&T::expandBy),
				"Grow the sphere in place to also contain a box."
			)
			.def("expandRadiusBy", static_cast<void(T::*)(const vec_type&)>(&T::expandBy),
				"Grow only the radius (never move the center) to also contain a point."
			)
			.def("expandRadiusBy", static_cast<void(T::*)(const T&)>(&T::expandBy),
				"Grow only the radius (never move the center) to also contain another sphere."
			)
			.def("expandRadiusBy", static_cast<void(T::*)(const osg::BoundingBox&)>(&T::expandBy),
				"Grow only the radius (never move the center) to also contain a box."
			)
			.def("intersects", &T::intersects, "Return whether this sphere overlaps another.")
			.def("contains", py::overload_cast<const vec_type&>(&T::contains, py::const_),
				"Return whether a point lies within the sphere."
			)
		;
	}
}

void bind_Bound(py::module_& m);

}
