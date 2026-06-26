#include "Uniform.hpp"

namespace pyosg {

void bind_Uniform(py::module_& m) {
	auto uniform = py::class_<osg::Uniform, osg::Object, osg::ref_ptr<osg::Uniform>>(m, "Uniform");

	py::enum_<osg::Uniform::Type>(uniform, "Type")
		.value("FLOAT", osg::Uniform::FLOAT)
		.value("FLOAT_VEC2", osg::Uniform::FLOAT_VEC2)
		.value("FLOAT_VEC3", osg::Uniform::FLOAT_VEC3)
		.value("FLOAT_VEC4", osg::Uniform::FLOAT_VEC4)

		.value("DOUBLE", osg::Uniform::DOUBLE)
		.value("DOUBLE_VEC2", osg::Uniform::DOUBLE_VEC2)
		.value("DOUBLE_VEC3", osg::Uniform::DOUBLE_VEC3)
		.value("DOUBLE_VEC4", osg::Uniform::DOUBLE_VEC4)

		.value("INT", osg::Uniform::INT)
		.value("INT_VEC2", osg::Uniform::INT_VEC2)
		.value("INT_VEC3", osg::Uniform::INT_VEC3)
		.value("INT_VEC4", osg::Uniform::INT_VEC4)

		.value("UNSIGNED_INT", osg::Uniform::UNSIGNED_INT)
		.value("UNSIGNED_INT_VEC2", osg::Uniform::UNSIGNED_INT_VEC2)
		.value("UNSIGNED_INT_VEC3", osg::Uniform::UNSIGNED_INT_VEC3)
		.value("UNSIGNED_INT_VEC4", osg::Uniform::UNSIGNED_INT_VEC4)

		.value("BOOL", osg::Uniform::BOOL)
		.value("BOOL_VEC2", osg::Uniform::BOOL_VEC2)
		.value("BOOL_VEC3", osg::Uniform::BOOL_VEC3)
		.value("BOOL_VEC4", osg::Uniform::BOOL_VEC4)

		.value("INT64", osg::Uniform::INT64)
		.value("UNSIGNED_INT64", osg::Uniform::UNSIGNED_INT64)

		.value("FLOAT_MAT2", osg::Uniform::FLOAT_MAT2)
		.value("FLOAT_MAT3", osg::Uniform::FLOAT_MAT3)
		.value("FLOAT_MAT4", osg::Uniform::FLOAT_MAT4)
		.value("FLOAT_MAT2x3", osg::Uniform::FLOAT_MAT2x3)
		.value("FLOAT_MAT2x4", osg::Uniform::FLOAT_MAT2x4)
		.value("FLOAT_MAT3x2", osg::Uniform::FLOAT_MAT3x2)
		.value("FLOAT_MAT3x4", osg::Uniform::FLOAT_MAT3x4)
		.value("FLOAT_MAT4x2", osg::Uniform::FLOAT_MAT4x2)
		.value("FLOAT_MAT4x3", osg::Uniform::FLOAT_MAT4x3)

		.value("DOUBLE_MAT2", osg::Uniform::DOUBLE_MAT2)
		.value("DOUBLE_MAT3", osg::Uniform::DOUBLE_MAT3)
		.value("DOUBLE_MAT4", osg::Uniform::DOUBLE_MAT4)
		.value("DOUBLE_MAT2x3", osg::Uniform::DOUBLE_MAT2x3)
		.value("DOUBLE_MAT2x4", osg::Uniform::DOUBLE_MAT2x4)
		.value("DOUBLE_MAT3x2", osg::Uniform::DOUBLE_MAT3x2)
		.value("DOUBLE_MAT3x4", osg::Uniform::DOUBLE_MAT3x4)
		.value("DOUBLE_MAT4x2", osg::Uniform::DOUBLE_MAT4x2)
		.value("DOUBLE_MAT4x3", osg::Uniform::DOUBLE_MAT4x3)

		.value("SAMPLER_1D", osg::Uniform::SAMPLER_1D)
		.value("SAMPLER_2D", osg::Uniform::SAMPLER_2D)
		.value("SAMPLER_3D", osg::Uniform::SAMPLER_3D)
		.value("SAMPLER_CUBE", osg::Uniform::SAMPLER_CUBE)
		.value("SAMPLER_1D_SHADOW", osg::Uniform::SAMPLER_1D_SHADOW)
		.value("SAMPLER_2D_SHADOW", osg::Uniform::SAMPLER_2D_SHADOW)
		.value("SAMPLER_1D_ARRAY", osg::Uniform::SAMPLER_1D_ARRAY)
		.value("SAMPLER_2D_ARRAY", osg::Uniform::SAMPLER_2D_ARRAY)
		.value("SAMPLER_CUBE_MAP_ARRAY", osg::Uniform::SAMPLER_CUBE_MAP_ARRAY)
		.value("SAMPLER_1D_ARRAY_SHADOW", osg::Uniform::SAMPLER_1D_ARRAY_SHADOW)
		.value("SAMPLER_2D_ARRAY_SHADOW", osg::Uniform::SAMPLER_2D_ARRAY_SHADOW)
		.value("SAMPLER_2D_MULTISAMPLE", osg::Uniform::SAMPLER_2D_MULTISAMPLE)
		.value("SAMPLER_2D_MULTISAMPLE_ARRAY", osg::Uniform::SAMPLER_2D_MULTISAMPLE_ARRAY)
		.value("SAMPLER_CUBE_SHADOW", osg::Uniform::SAMPLER_CUBE_SHADOW)
		.value("SAMPLER_CUBE_MAP_ARRAY_SHADOW", osg::Uniform::SAMPLER_CUBE_MAP_ARRAY_SHADOW)
		.value("SAMPLER_BUFFER", osg::Uniform::SAMPLER_BUFFER)
		.value("SAMPLER_2D_RECT", osg::Uniform::SAMPLER_2D_RECT)
		.value("SAMPLER_2D_RECT_SHADOW", osg::Uniform::SAMPLER_2D_RECT_SHADOW)

		.value("INT_SAMPLER_1D", osg::Uniform::INT_SAMPLER_1D)
		.value("INT_SAMPLER_2D", osg::Uniform::INT_SAMPLER_2D)
		.value("INT_SAMPLER_3D", osg::Uniform::INT_SAMPLER_3D)
		.value("INT_SAMPLER_CUBE", osg::Uniform::INT_SAMPLER_CUBE)
		.value("INT_SAMPLER_1D_ARRAY", osg::Uniform::INT_SAMPLER_1D_ARRAY)
		.value("INT_SAMPLER_2D_ARRAY", osg::Uniform::INT_SAMPLER_2D_ARRAY)
		.value("INT_SAMPLER_CUBE_MAP_ARRAY", osg::Uniform::INT_SAMPLER_CUBE_MAP_ARRAY)
		.value("INT_SAMPLER_2D_MULTISAMPLE", osg::Uniform::INT_SAMPLER_2D_MULTISAMPLE)
		.value("INT_SAMPLER_2D_MULTISAMPLE_ARRAY", osg::Uniform::INT_SAMPLER_2D_MULTISAMPLE_ARRAY)
		.value("INT_SAMPLER_BUFFER", osg::Uniform::INT_SAMPLER_BUFFER)
		.value("INT_SAMPLER_2D_RECT", osg::Uniform::INT_SAMPLER_2D_RECT)

		.value("UNSIGNED_INT_SAMPLER_1D", osg::Uniform::UNSIGNED_INT_SAMPLER_1D)
		.value("UNSIGNED_INT_SAMPLER_2D", osg::Uniform::UNSIGNED_INT_SAMPLER_2D)
		.value("UNSIGNED_INT_SAMPLER_3D", osg::Uniform::UNSIGNED_INT_SAMPLER_3D)
		.value("UNSIGNED_INT_SAMPLER_CUBE", osg::Uniform::UNSIGNED_INT_SAMPLER_CUBE)
		.value("UNSIGNED_INT_SAMPLER_1D_ARRAY", osg::Uniform::UNSIGNED_INT_SAMPLER_1D_ARRAY)
		.value("UNSIGNED_INT_SAMPLER_2D_ARRAY", osg::Uniform::UNSIGNED_INT_SAMPLER_2D_ARRAY)
		.value("UNSIGNED_INT_SAMPLER_CUBE_MAP_ARRAY", osg::Uniform::UNSIGNED_INT_SAMPLER_CUBE_MAP_ARRAY)
		.value("UNSIGNED_INT_SAMPLER_2D_MULTISAMPLE", osg::Uniform::UNSIGNED_INT_SAMPLER_2D_MULTISAMPLE)
		.value("UNSIGNED_INT_SAMPLER_2D_MULTISAMPLE_ARRAY", osg::Uniform::UNSIGNED_INT_SAMPLER_2D_MULTISAMPLE_ARRAY)
		.value("UNSIGNED_INT_SAMPLER_BUFFER", osg::Uniform::UNSIGNED_INT_SAMPLER_BUFFER)
		.value("UNSIGNED_INT_SAMPLER_2D_RECT", osg::Uniform::UNSIGNED_INT_SAMPLER_2D_RECT)

		.value("IMAGE_1D", osg::Uniform::IMAGE_1D)
		.value("IMAGE_2D", osg::Uniform::IMAGE_2D)
		.value("IMAGE_3D", osg::Uniform::IMAGE_3D)
		.value("IMAGE_2D_RECT", osg::Uniform::IMAGE_2D_RECT)
		.value("IMAGE_CUBE", osg::Uniform::IMAGE_CUBE)
		.value("IMAGE_BUFFER", osg::Uniform::IMAGE_BUFFER)
		.value("IMAGE_1D_ARRAY", osg::Uniform::IMAGE_1D_ARRAY)
		.value("IMAGE_2D_ARRAY", osg::Uniform::IMAGE_2D_ARRAY)
		.value("IMAGE_CUBE_MAP_ARRAY", osg::Uniform::IMAGE_CUBE_MAP_ARRAY)
		.value("IMAGE_2D_MULTISAMPLE", osg::Uniform::IMAGE_2D_MULTISAMPLE)
		.value("IMAGE_2D_MULTISAMPLE_ARRAY", osg::Uniform::IMAGE_2D_MULTISAMPLE_ARRAY)

		.value("INT_IMAGE_1D", osg::Uniform::INT_IMAGE_1D)
		.value("INT_IMAGE_2D", osg::Uniform::INT_IMAGE_2D)
		.value("INT_IMAGE_3D", osg::Uniform::INT_IMAGE_3D)
		.value("INT_IMAGE_2D_RECT", osg::Uniform::INT_IMAGE_2D_RECT)
		.value("INT_IMAGE_CUBE", osg::Uniform::INT_IMAGE_CUBE)
		.value("INT_IMAGE_BUFFER", osg::Uniform::INT_IMAGE_BUFFER)
		.value("INT_IMAGE_1D_ARRAY", osg::Uniform::INT_IMAGE_1D_ARRAY)
		.value("INT_IMAGE_2D_ARRAY", osg::Uniform::INT_IMAGE_2D_ARRAY)
		.value("INT_IMAGE_CUBE_MAP_ARRAY", osg::Uniform::INT_IMAGE_CUBE_MAP_ARRAY)
		.value("INT_IMAGE_2D_MULTISAMPLE", osg::Uniform::INT_IMAGE_2D_MULTISAMPLE)
		.value("INT_IMAGE_2D_MULTISAMPLE_ARRAY", osg::Uniform::INT_IMAGE_2D_MULTISAMPLE_ARRAY)

		.value("UNSIGNED_INT_IMAGE_1D", osg::Uniform::UNSIGNED_INT_IMAGE_1D)
		.value("UNSIGNED_INT_IMAGE_2D", osg::Uniform::UNSIGNED_INT_IMAGE_2D)
		.value("UNSIGNED_INT_IMAGE_3D", osg::Uniform::UNSIGNED_INT_IMAGE_3D)
		.value("UNSIGNED_INT_IMAGE_2D_RECT", osg::Uniform::UNSIGNED_INT_IMAGE_2D_RECT)
		.value("UNSIGNED_INT_IMAGE_CUBE", osg::Uniform::UNSIGNED_INT_IMAGE_CUBE)
		.value("UNSIGNED_INT_IMAGE_BUFFER", osg::Uniform::UNSIGNED_INT_IMAGE_BUFFER)
		.value("UNSIGNED_INT_IMAGE_1D_ARRAY", osg::Uniform::UNSIGNED_INT_IMAGE_1D_ARRAY)
		.value("UNSIGNED_INT_IMAGE_2D_ARRAY", osg::Uniform::UNSIGNED_INT_IMAGE_2D_ARRAY)
		.value("UNSIGNED_INT_IMAGE_CUBE_MAP_ARRAY", osg::Uniform::UNSIGNED_INT_IMAGE_CUBE_MAP_ARRAY)
		.value("UNSIGNED_INT_IMAGE_2D_MULTISAMPLE", osg::Uniform::UNSIGNED_INT_IMAGE_2D_MULTISAMPLE)
		.value("UNSIGNED_INT_IMAGE_2D_MULTISAMPLE_ARRAY", osg::Uniform::UNSIGNED_INT_IMAGE_2D_MULTISAMPLE_ARRAY)

		.value("UNDEFINED", osg::Uniform::UNDEFINED)

		.export_values()
	;

#if 0
        /** Get the number of elements required for the internal data array.
          * Returns 0 if the osg::Uniform is not properly configured.  */
        unsigned int getInternalArrayNumElements() const;

        bool operator <  (const Uniform& rhs) const { return compare(rhs)<0; }
        bool operator == (const Uniform& rhs) const { return compare(rhs)==0; }
        bool operator != (const Uniform& rhs) const { return compare(rhs)!=0; }
#endif

	py::class_<detail::UniformIterator>(uniform, "_UniformIterator", py::module_local())
		.def("__iter__", [](detail::UniformIterator& self) -> detail::UniformIterator& {
			return self;
		}, py::return_value_policy::reference_internal)
		.def("__next__", &detail::UniformIterator::next)
	;

	uniform
		.def(py::init<>())
		.def(py::init<const osg::Uniform&>())
		.def(
			py::init<osg::Uniform::Type, const std::string&, int>(),
			"type"_a,
			"name"_a,
			"numElements"_a=1
		)

		/* .def(py::init<const char*, double>())
		.def(py::init<const char*, unsigned long long>())
		.def(py::init<const char*, long long>()) */

		.def(py::init<const char*, const osg::Vec2&>())
		.def(py::init<const char*, const osg::Vec3&>())
		.def(py::init<const char*, const osg::Vec4&>())

		/* .def(py::init<const char*, const osg::Vec2d&>())
		.def(py::init<const char*, const osg::Vec3d&>())
		.def(py::init<const char*, const osg::Vec4d&>())

		.def(py::init<const char*, const osg::Matrix2&>())
		.def(py::init<const char*, const osg::Matrix3&>())
		.def(py::init<const char*, const osg::Matrixf&>())

		.def(py::init<const char*, const osg::Matrix2x3&>())
		.def(py::init<const char*, const osg::Matrix2x4&>())
		.def(py::init<const char*, const osg::Matrix3x2&>())
		.def(py::init<const char*, const osg::Matrix3x4&>())
		.def(py::init<const char*, const osg::Matrix4x2&>())
		.def(py::init<const char*, const osg::Matrix4x3&>())

		.def(py::init<const char*, const osg::Matrix2d&>())
		.def(py::init<const char*, const osg::Matrix3d&>())
		.def(py::init<const char*, const osg::Matrixd&>())

		.def(py::init<const char*, const osg::Matrix2x3d&>())
		.def(py::init<const char*, const osg::Matrix2x4d&>())
		.def(py::init<const char*, const osg::Matrix3x2d&>())
		.def(py::init<const char*, const osg::Matrix3x4d&>())
		.def(py::init<const char*, const osg::Matrix4x2d&>())
		.def(py::init<const char*, const osg::Matrix4x3d&>()) */

		.def(py::init<const char*, const osg::Matrixf&>())
		.def(py::init<const char*, const osg::Matrixd&>())

		.def(py::init<const char*, int, int>())
		.def(py::init<const char*, int, int, int>())
		.def(py::init<const char*, int, int, int, int>())

		.def(py::init<const char*, unsigned int, unsigned int>())
		.def(py::init<const char*, unsigned int, unsigned int, unsigned int>())
		.def(py::init<const char*, unsigned int, unsigned int, unsigned int, unsigned int>())

		.def(py::init<const char*, bool, bool>())
		.def(py::init<const char*, bool, bool, bool>())
		.def(py::init<const char*, bool, bool, bool, bool>())

		.def(py::init([](const char* name, py::object obj) {
			if(py::isinstance<py::bool_>(obj)) return new osg::Uniform(name, obj.cast<bool>());

			if(py::isinstance<py::int_>(obj)) return new osg::Uniform(name, obj.cast<int>());

			if(py::isinstance<py::float_>(obj)) return new osg::Uniform(name, obj.cast<float>());

			throw py::type_error("Unsupported type for Uniform(name, value)");
		}))

		.def_property("type", &osg::Uniform::getType, &osg::Uniform::setType)
		.def_property("numElements", &osg::Uniform::getNumElements, &osg::Uniform::setNumElements)
		.def_property_readonly("nameID", py::overload_cast<>(&osg::Uniform::getNameID, py::const_))

		.def_property(
			"value",
			[](osg::Uniform& self) {
				if(self.getNumElements() != 1) throw py::value_error(
					"value property only valid for single-element Uniforms"
				);

				return detail::uniform_get(self, 0);
			},
			[](osg::Uniform& self, py::object obj) {
				if(self.getNumElements() != 1) throw py::value_error(
					"value property only valid for single-element Uniforms"
				);

				/* // --- tuple override ---
				if(py::isinstance<py::tuple>(obj)) {
					auto t = py::cast<py::tuple>(obj);

					if(t.size() < 2 || t.size() > 3)
						throw py::type_error("Uniform tuple must be (type, value[, mode])");

					auto type = t[0].cast<osg::Uniform::Type>();
					auto value = t[1];

					self.setType(type);
					detail::uniform_set(self, 0, value);
					return;
				} */

				detail::uniform_set(self, 0, obj);
			}
		)

		// TODO: This needs lots of testing!
		.def_property("array", &detail::uniform_get_array, &detail::uniform_set_array)

		.def("dirty", &osg::Uniform::dirty)
		.def("__len__", [](const osg::Uniform& self) { return self.getNumElements(); })
		.def("__getitem__", &detail::uniform_get, py::return_value_policy::reference_internal)
		.def("__setitem__", &detail::uniform_set)
		.def("__iter__", [](osg::Uniform& self) { return detail::UniformIterator{&self, 0}; })

		.def_static("getTypename", &osg::Uniform::getTypename)
		.def_static("getTypeNumComponents", &osg::Uniform::getTypeNumComponents)
		.def_static("getTypeId", &osg::Uniform::getTypeId)
		.def_static("getGlApiType", &osg::Uniform::getGlApiType)
		.def_static("getInternalArrayType", &osg::Uniform::getInternalArrayType)
		.def_static("getNameID", py::overload_cast<const std::string&>(&osg::Uniform::getNameID))
	;
}

}
