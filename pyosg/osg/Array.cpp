#include "Array.hpp"

namespace pyosg {

void bind_Array(py::module_& m) {
	auto arr = py::class_<
		osg::Array,
		osg::BufferData,
		osg::ref_ptr<osg::Array>
	>(m, "Array")
		.def_property_readonly("type", &osg::Array::getType)
		.def_property_readonly("dataSize", &osg::Array::getDataSize)
		.def_property_readonly("dataType", &osg::Array::getDataType)
		.def_property("binding", &osg::Array::getBinding, &osg::Array::setBinding)
		.def_property("normalize", &osg::Array::getNormalize, &osg::Array::setNormalize)
	;

	py::enum_<osg::Array::Type>(arr, "Type")
		.value("ArrayType", osg::Array::ArrayType)
		.value("ByteArrayType", osg::Array::ByteArrayType)
		.value("FloatArrayType", osg::Array::FloatArrayType)
		.value("Vec2ArrayType", osg::Array::Vec2ArrayType)
		.value("Vec3ArrayType", osg::Array::Vec3ArrayType)
		.value("Vec4ArrayType", osg::Array::Vec4ArrayType)
	;

	py::enum_<osg::Array::Binding>(arr, "Binding")
		.value("BIND_UNDEFINED", osg::Array::BIND_UNDEFINED)
		.value("BIND_OFF", osg::Array::BIND_OFF)
		.value("BIND_OVERALL", osg::Array::BIND_OVERALL)
		.value("BIND_PER_PRIMITIVE_SET", osg::Array::BIND_PER_PRIMITIVE_SET)
		.value("BIND_PER_VERTEX", osg::Array::BIND_PER_VERTEX)
		.export_values()
	;

	detail::bind_Array<osg::ByteArray>(m, "ByteArray");
	detail::bind_Array<osg::FloatArray>(m, "FloatArray");
	detail::bind_Array<osg::Vec2Array>(m, "Vec2Array");
	detail::bind_Array<osg::Vec3Array>(m, "Vec3Array");
	detail::bind_Array<osg::Vec4Array>(m, "Vec4Array");
}

}
