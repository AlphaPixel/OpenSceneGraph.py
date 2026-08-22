#include "../pyosg.hpp"

OSGX_DISABLE_WARNINGS

#include <osg/Quat>

OSGX_ENABLE_WARNINGS

namespace pyosg {

using value_type = osg::Quat::value_type;

namespace detail {
	template<size_t I>
	constexpr auto quat_get() { return [](const osg::Quat& q) -> value_type { return q[I]; }; }

	template<size_t I>
	constexpr auto quat_set() { return [](osg::Quat& q, value_type val) { q[I] = val; }; }
}

void bind_Quat(py::module_& m) {
	auto quat = py::class_<osg::Quat>(m, "Quat")
		.def(py::init<>())
		.def(py::init<const osg::Quat&>())
		.def(py::init<const osg::Vec4f&>())
		.def(py::init<const osg::Vec4d&>())
		.def(py::init<value_type, const osg::Vec3f&>())
		.def(py::init<value_type, const osg::Vec3d&>())
		.def(py::init<
			value_type, const osg::Vec3f&,
			value_type, const osg::Vec3f&,
			value_type, const osg::Vec3f&
		>())
		.def(py::init<
			value_type, const osg::Vec3d&,
			value_type, const osg::Vec3d&,
			value_type, const osg::Vec3d&
		>())

		.def(py::self * py::self)
		.def(py::self * value_type())
		.def(py::self * osg::Vec3f())
		.def(py::self * osg::Vec3d())
		.def(py::self *= py::self)
		.def(py::self *= value_type())
		.def(py::self / py::self)
		.def(py::self / value_type())
		.def(py::self /= py::self)
		.def(py::self /= value_type())
		.def(py::self + py::self)
		.def(py::self += py::self)
		.def(py::self - py::self)
		.def(py::self -= py::self)
		.def(-py::self)
		.def("length", &osg::Quat::length)
		.def("length2", &osg::Quat::length2)
		.def("conj", &osg::Quat::conj)
		.def("inverse", &osg::Quat::inverse)
		.def("slerp", &osg::Quat::slerp)

		.def("makeRotate", py::overload_cast<
			value_type,
			value_type,
			value_type,
			value_type
		>(&osg::Quat::makeRotate))
		.def("makeRotate", py::overload_cast<
			value_type,
			const osg::Vec3f&
		>(&osg::Quat::makeRotate))
		.def("makeRotate", py::overload_cast<
			value_type,
			const osg::Vec3d&
		>(&osg::Quat::makeRotate))
		.def("makeRotate", py::overload_cast<
			value_type, const osg::Vec3f&,
			value_type, const osg::Vec3f&,
			value_type, const osg::Vec3f&
		>(&osg::Quat::makeRotate))
		.def("makeRotate", py::overload_cast<
			value_type, const osg::Vec3d&,
			value_type, const osg::Vec3d&,
			value_type, const osg::Vec3d&
		>(&osg::Quat::makeRotate))
		.def("makeRotate", py::overload_cast<
			const osg::Vec3f&,
			const osg::Vec3f&
		>(&osg::Quat::makeRotate))
		.def("makeRotate", py::overload_cast<
			const osg::Vec3d&,
			const osg::Vec3d&
		>(&osg::Quat::makeRotate))
		.def("getRotate", [](const osg::Quat& self) {
			value_type angle;

			if constexpr(std::is_same_v<value_type, float>) {
				osg::Vec3f axis;

				self.getRotate(angle, axis);

				return py::make_tuple(angle, axis);
			}

			else {
				osg::Vec3d axis;

				self.getRotate(angle, axis);

				return py::make_tuple(angle, axis);
			}
		})

		.def("__eq__", [](const osg::Quat& a, const osg::Quat& b) { return a == b; })

		.def("__len__", [](const osg::Quat&){ return 4; })

		.def("__iter__", [](const osg::Quat& v){
			py::tuple t(4);

			OSGX_DISABLE_WARNINGS

				for(size_t i = 0; i < 4; i++) t[i] = v[i];

			OSGX_ENABLE_WARNINGS

			return py::iter(t);
		})

		.def("__repr__", [](const osg::Quat& v) {
			return detail::seq_repr<4>("Quat", [&](size_t i) {
				OSGX_DISABLE_WARNINGS

					return v[i];

				OSGX_ENABLE_WARNINGS
			});
		})
	;

	OSGX_DISABLE_WARNINGS

		quat
			.def("__getitem__", [](const osg::Quat& v, py::ssize_t i) {
				return v[detail::n_index(4, i)];
			})

			.def("__setitem__", [](osg::Quat& v, py::ssize_t i, value_type val){
				v[detail::n_index(4, i)] = val;
			})
		;

	OSGX_ENABLE_WARNINGS

	quat
		.def_property_readonly("zeroRotation", &osg::Quat::zeroRotation)
		.def_property("x", detail::quat_get<0>(), detail::quat_set<0>())
		.def_property("y", detail::quat_get<1>(), detail::quat_set<1>())
		.def_property("z", detail::quat_get<2>(), detail::quat_set<2>())
		.def_property("w", detail::quat_get<3>(), detail::quat_set<3>())
	;
}

}
