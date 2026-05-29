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
		// .def_property("bufferObject"
		// .def_property("bufferIndex"
	;

	py::enum_<osg::Array::Type>(arr, "Type")
		.value("ArrayType", osg::Array::ArrayType)
		.value("ByteArrayType", osg::Array::ByteArrayType)
		.value("FloatArrayType", osg::Array::FloatArrayType)
		.value("Vec2ArrayType", osg::Array::Vec2ArrayType)
		.value("Vec3ArrayType", osg::Array::Vec3ArrayType)
		.value("Vec4ArrayType", osg::Array::Vec4ArrayType)
	;

	detail::bind_Array<osg::ByteArray>(m, "ByteArray");
	detail::bind_Array<osg::FloatArray>(m, "FloatArray");
	detail::bind_Array<osg::Vec2Array>(m, "Vec2Array");
	detail::bind_Array<osg::Vec3Array>(m, "Vec3Array");
	detail::bind_Array<osg::Vec4Array>(m, "Vec4Array");
}

}
