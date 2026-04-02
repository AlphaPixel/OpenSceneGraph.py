#include "../pyosg.hpp"

PYOSG_DISABLE_WARNINGS

#include <osg/Quat>

PYOSG_ENABLE_WARNINGS

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

			// osg::Vec3f axis;
			// osg::Vec3d axis;

			// self.getRotate(angle, axis);

			// return py::make_tuple(angle, axis);
		})
	;

#if 0
		.def("__eq__", [](const osg::Quat& a, const osg::Quat& b) { return a == b; })

		.def("__len__", [](const osg::Quat&){ return N; })

		.def("__iter__", [](const osg::Quat& v){
			py::tuple t(N);

			PYOSG_DISABLE_WARNINGS

				for(size_t i = 0; i < N; i++) t[i] = v[i];

			PYOSG_ENABLE_WARNINGS

			return py::iter(t);
		})

		.def("__repr__", [name](const osg::Quat& v) {
			return seq_repr<N>(name, [&](size_t i) {
				PYOSG_DISABLE_WARNINGS

					return v[i];

				PYOSG_ENABLE_WARNINGS
			});

			/* py::list items;

			for(size_t i = 0; i < N; i++) {
				PYOSG_DISABLE_WARNINGS

					// No matter WHAosg::Quat the value_type is, lets give Python a double... a nice
					// side-effect of how Python handles float-point numbers is that the
					// `repr()` value of any true float-based type will CLEARLY indicate how a
					// true 32bit float will look to the GPU!
					auto val = py::float_(static_cast<double>(v[i]));

				PYOSG_ENABLE_WARNINGS

				items.append(py::repr(val));
			}

			return py::str("{}({})").format(name, py::str(", ").attr("join")(items)); */
		})
#endif

	PYOSG_DISABLE_WARNINGS

		quat
			.def("__getitem__", [](const osg::Quat& v, py::ssize_t i) {
				return v[detail::n_index(4, i)];
			})

			.def("__setitem__", [](osg::Quat& v, py::ssize_t i, value_type val){
				v[detail::n_index(4, i)] = val;
			})
		;

	PYOSG_ENABLE_WARNINGS

	quat
		.def_property_readonly("zeroRotation", &osg::Quat::zeroRotation)
		.def_property("x", detail::quat_get<0>(), detail::quat_set<0>())
		.def_property("y", detail::quat_get<1>(), detail::quat_set<1>())
		.def_property("z", detail::quat_get<2>(), detail::quat_set<2>())
		.def_property("w", detail::quat_get<3>(), detail::quat_set<3>())
	;
}

}
