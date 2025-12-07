#include "../pyosg.hpp"

PYOSG_DISABLE_WARNINGS

#include <osg/BoundingBox>
#include <osg/BoundingSphere>

PYOSG_ENABLE_WARNINGS

namespace pyosg {

namespace detail {
	template<typename T>
	auto bind_BoundingBox(py::module_& m, const char* name) {
		using vec_type = typename T::vec_type;
		using value_type = typename T::value_type;

		return py::class_<T>(m, name)
			.def(py::init<>())
			.def(py::init<const T&>())
			.def(py::init<
				value_type, value_type, value_type,
				value_type, value_type, value_type
			>())
			.def(py::init<const vec_type&, const vec_type&>())
			.def(py::init<const T&>())
			.def(py::self == py::self)
			.def(py::self != py::self)
			.def("valid", &T::valid)
			.def_property("xMin",
				py::overload_cast<>(&T::xMin, py::const_),
				[](T& self, value_type v) { self.xMin() = v; }
			)
			.def_property("xMax",
				py::overload_cast<>(&T::xMax, py::const_),
				[](T& self, value_type v) { self.xMax() = v; }
			)
			.def_property("yMin",
				py::overload_cast<>(&T::yMin, py::const_),
				[](T& self, value_type v) { self.yMin() = v; }
			)
			.def_property("yMax",
				py::overload_cast<>(&T::yMax, py::const_),
				[](T& self, value_type v) { self.yMax() = v; }
			)
			.def_property("zMin",
				py::overload_cast<>(&T::zMin, py::const_),
				[](T& self, value_type v) { self.zMin() = v; }
			)
			.def_property("zMax",
				py::overload_cast<>(&T::zMax, py::const_),
				[](T& self, value_type v) { self.zMax() = v; }
			)
			.def_property_readonly("center", &T::center)
			.def_property_readonly("radius", &T::radius)
			.def_property_readonly("radius2", &T::radius2)
			.def("corner", &T::corner)
			.def("expandBy", static_cast<void(T::*)(const vec_type&)>(&T::expandBy))
			.def("expandBy", static_cast<void(T::*)(const T&)>(&T::expandBy))
			.def("expandBy", static_cast<void(T::*)(const osg::BoundingSphere&)>(&T::expandBy))
			.def("intersect", &T::intersect)
			.def("intersects", &T::intersects)
			.def("contains", py::overload_cast<const vec_type&>(&T::contains, py::const_))
			.def("contains", py::overload_cast<const vec_type&, value_type>(&T::contains, py::const_))
		;
	}

	template<typename T>
	auto bind_BoundingSphere(py::module_& m, const char* name) {
		using vec_type = typename T::vec_type;
		using value_type = typename T::value_type;

		return py::class_<T>(m, name)
			.def(py::init<>())
			.def(py::init<const T&>())
			.def(py::init<const vec_type&, value_type>())
			.def(py::self == py::self)
			.def(py::self != py::self)
			.def("valid", &T::valid)
			.def_property("center",
				py::overload_cast<>(&T::center, py::const_),
				[](T& self, vec_type v) { self.center() = v; }
			)
			.def_property("radius",
				py::overload_cast<>(&T::radius, py::const_),
				[](T& self, value_type v) { self.radius() = v; }
			)
			.def_property_readonly("radius2", &T::radius2)
			.def("expandBy", static_cast<void(T::*)(const vec_type&)>(&T::expandBy))
			.def("expandBy", static_cast<void(T::*)(const T&)>(&T::expandBy))
			.def("expandBy", static_cast<void(T::*)(const osg::BoundingBox&)>(&T::expandBy))
			.def("expandRadiusBy", static_cast<void(T::*)(const vec_type&)>(&T::expandBy))
			.def("expandRadiusBy", static_cast<void(T::*)(const T&)>(&T::expandBy))
			.def("expandRadiusBy", static_cast<void(T::*)(const osg::BoundingBox&)>(&T::expandBy))
			.def("intersects", &T::intersects)
			.def("contains", py::overload_cast<const vec_type&>(&T::contains, py::const_))
		;
	}
}

void bind_Bound(py::module_& m) {
	auto bbf = detail::bind_BoundingBox<osg::BoundingBoxf>(m, "BoundingBoxf");
	auto bbd = detail::bind_BoundingBox<osg::BoundingBoxd>(m, "BoundingBoxd");

#ifdef OSG_USE_FLOAT_BOUNDINGBOX
	m.add_object("BoundingBox", bbf);
#else
	m.add_object("BoundingBox", bbd);
#endif

	auto bsf = detail::bind_BoundingSphere<osg::BoundingSpheref>(m, "BoundingSpheref");
	auto bsd = detail::bind_BoundingSphere<osg::BoundingSphered>(m, "BoundingSphered");

#ifdef OSG_USE_FLOAT_BOUNDINGSPHERE
	m.add_object("BoundingSphere", bsf);
#else
	m.add_object("BoundingSphere", bsf);
#endif
}

}
