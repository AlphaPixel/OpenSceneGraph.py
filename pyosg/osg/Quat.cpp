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
	auto quat = py::class_<osg::Quat>(
		m,
		"Quat",
		"A quaternion for representing and composing 3D rotations, with the usual "
		"multiply/slerp/inverse operations."
	)
		.def(py::init<>(), "Create the identity quaternion, representing no rotation.")
		.def(py::init<const osg::Quat&>(), "Create a copy of another quaternion.")
		.def(py::init<const osg::Vec4f&>(),
			"Create a quaternion from a four-component float vector."
		)
		.def(py::init<const osg::Vec4d&>(),
			"Create a quaternion from a four-component double vector."
		)
		.def(py::init<value_type, const osg::Vec3f&>(),
			"Create a rotation from an angle in radians and a float axis."
		)
		.def(py::init<value_type, const osg::Vec3d&>(),
			"Create a rotation from an angle in radians and a double axis."
		)
		.def(py::init<
			value_type, const osg::Vec3f&,
			value_type, const osg::Vec3f&,
			value_type, const osg::Vec3f&
		>(), "Create a rotation by composing three float axis-angle rotations.")
		.def(py::init<
			value_type, const osg::Vec3d&,
			value_type, const osg::Vec3d&,
			value_type, const osg::Vec3d&
		>(), "Create a rotation by composing three double axis-angle rotations.")

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
		.def("length", &osg::Quat::length, "Return the quaternion's Euclidean length.")
		.def("length2", &osg::Quat::length2,
			"Return the square of the quaternion's Euclidean length."
		)
		.def("conj", &osg::Quat::conj, "Return the conjugate quaternion.")
		.def("inverse", &osg::Quat::inverse, "Return the multiplicative inverse quaternion.")
		.def("slerp", &osg::Quat::slerp,
			"Set this quaternion to the spherical interpolation from `from` to `to` at t."
		)

		.def("makeRotate", py::overload_cast<
			value_type,
			value_type,
			value_type,
			value_type
		>(&osg::Quat::makeRotate),
			"Set this quaternion to the axis-angle rotation given by angle, x, y, and z."
		)
		.def("makeRotate", py::overload_cast<
			value_type,
			const osg::Vec3f&
		>(&osg::Quat::makeRotate),
			"Set this quaternion to an axis-angle rotation using a float axis."
		)
		.def("makeRotate", py::overload_cast<
			value_type,
			const osg::Vec3d&
		>(&osg::Quat::makeRotate),
			"Set this quaternion to an axis-angle rotation using a double axis."
		)
		.def("makeRotate", py::overload_cast<
			value_type, const osg::Vec3f&,
			value_type, const osg::Vec3f&,
			value_type, const osg::Vec3f&
		>(&osg::Quat::makeRotate),
			"Set this quaternion by composing three float axis-angle rotations."
		)
		.def("makeRotate", py::overload_cast<
			value_type, const osg::Vec3d&,
			value_type, const osg::Vec3d&,
			value_type, const osg::Vec3d&
		>(&osg::Quat::makeRotate),
			"Set this quaternion by composing three double axis-angle rotations."
		)
		.def("makeRotate", py::overload_cast<
			const osg::Vec3f&,
			const osg::Vec3f&
		>(&osg::Quat::makeRotate),
			"Set this quaternion to rotate one float direction vector to another."
		)
		.def("makeRotate", py::overload_cast<
			const osg::Vec3d&,
			const osg::Vec3d&
		>(&osg::Quat::makeRotate),
			"Set this quaternion to rotate one double direction vector to another."
		)
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
		},
			"Return this rotation as an (angle, axis) tuple."
		)

		.def("__eq__", [](const osg::Quat& a, const osg::Quat& b) { return a == b; },
			"Return whether all four components equal those of another quaternion."
		)

		.def("__len__", [](const osg::Quat&){ return 4; },
			"Return the number of quaternion components, always 4."
		)

		.def("__iter__", [](const osg::Quat& v){
			py::tuple t(4);

			OSGX_DISABLE_WARNINGS

				for(size_t i = 0; i < 4; i++) t[i] = v[i];

			OSGX_ENABLE_WARNINGS

			return py::iter(t);
		}, "Iterate over the x, y, z, and w components.")

		.def("__repr__", [](const osg::Quat& v) {
			return detail::seq_repr<4>("Quat", [&](size_t i) {
				OSGX_DISABLE_WARNINGS

					return v[i];

				OSGX_ENABLE_WARNINGS
			});
		}, "Return a constructor-style representation of this quaternion.")
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
