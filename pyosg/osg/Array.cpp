#include "Array.hpp"

namespace pyosg {

void bind_Array(py::module_& m) {
	auto arr = py::class_<
		osg::Array,
		osg::BufferData,
		osg::ref_ptr<osg::Array>
	>(
		m,
		"Array",
		"Base class for typed vertex/attribute arrays (ByteArray, FloatArray, Vec2Array, "
		"Vec3Array, Vec4Array) bound to a Geometry or GPU buffer object."
	)
		.def_property_readonly(
			"type",
			&osg::Array::getType,
			"The concrete element type of this array, as an Array.Type value."
		)
		.def_property_readonly(
			"dataSize",
			&osg::Array::getDataSize,
			"The number of scalar components per element (e.g. 3 for a Vec3Array)."
		)
		.def_property_readonly(
			"dataType",
			&osg::Array::getDataType,
			"The GL scalar type (e.g. GL_FLOAT) of each component in this array."
		)
		.def_property(
			"binding",
			&osg::Array::getBinding,
			&osg::Array::setBinding,
			"How this array's elements map to vertices/primitives (Array.Binding); "
			"BIND_PER_VERTEX for per-vertex attributes like normal or color arrays."
		)
		.def_property(
			"normalize",
			&osg::Array::getNormalize,
			&osg::Array::setNormalize,
			"Whether integer-typed elements are normalized to [0,1]/[-1,1] when read by the GPU."
		)
	;

	py::enum_<osg::Array::Type>(
		arr,
		"Type",
		"Identifies an Array's concrete element type (ByteArray/FloatArray/Vec2Array/...)."
	)
		.value("ArrayType", osg::Array::ArrayType)
		.value("ByteArrayType", osg::Array::ByteArrayType)
		.value("FloatArrayType", osg::Array::FloatArrayType)
		.value("Vec2ArrayType", osg::Array::Vec2ArrayType)
		.value("Vec3ArrayType", osg::Array::Vec3ArrayType)
		.value("Vec4ArrayType", osg::Array::Vec4ArrayType)
		.export_values()
	;

	py::enum_<osg::Array::Binding>(
		arr,
		"Binding",
		"How an Array's elements associate with vertices/primitives/the whole Geometry."
	)
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
