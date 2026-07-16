#include "Geometry.hpp"

namespace pyosg {

void bind_Geometry(py::module_& m) {
	py::class_<osg::PrimitiveFunctor>(m, "PrimitiveFunctor");
	py::class_<osg::PrimitiveIndexFunctor>(m, "PrimitiveIndexFunctor");

	auto ps = py::class_<
		osg::PrimitiveSet,
		detail::PrimitiveSet,
		osg::BufferData,
		osg::ref_ptr<osg::PrimitiveSet>
	>(m, "PrimitiveSet");

	py::enum_<osg::PrimitiveSet::Type>(ps, "Type")
		.value("PrimitiveType", osg::PrimitiveSet::PrimitiveType)
		.value("DrawArraysPrimitiveType", osg::PrimitiveSet::DrawArraysPrimitiveType)
		.value("DrawArrayLengthsPrimitiveType", osg::PrimitiveSet::DrawArrayLengthsPrimitiveType)
		.value("DrawElementsUBytePrimitiveType", osg::PrimitiveSet::DrawElementsUBytePrimitiveType)
		.value("DrawElementsUShortPrimitiveType", osg::PrimitiveSet::DrawElementsUShortPrimitiveType)
		.value("DrawElementsUIntPrimitiveType", osg::PrimitiveSet::DrawElementsUIntPrimitiveType)
		.value("MultiDrawArraysPrimitiveType", osg::PrimitiveSet::MultiDrawArraysPrimitiveType)
		.value("DrawArraysIndirectPrimitiveType", osg::PrimitiveSet::DrawArraysIndirectPrimitiveType)
		.value("DrawElementsUByteIndirectPrimitiveType", osg::PrimitiveSet::DrawElementsUByteIndirectPrimitiveType)
		.value("DrawElementsUShortIndirectPrimitiveType", osg::PrimitiveSet::DrawElementsUShortIndirectPrimitiveType)
		.value("DrawElementsUIntIndirectPrimitiveType", osg::PrimitiveSet::DrawElementsUIntIndirectPrimitiveType)
		.value("MultiDrawArraysIndirectPrimitiveType", osg::PrimitiveSet::MultiDrawArraysIndirectPrimitiveType)
		.value("MultiDrawElementsUByteIndirectPrimitiveType", osg::PrimitiveSet::MultiDrawElementsUByteIndirectPrimitiveType)
		.value("MultiDrawElementsUShortIndirectPrimitiveType", osg::PrimitiveSet::MultiDrawElementsUShortIndirectPrimitiveType)
		.value("MultiDrawElementsUIntIndirectPrimitiveType", osg::PrimitiveSet::MultiDrawElementsUIntIndirectPrimitiveType)
		.export_values()
	;

	py::enum_<osg::PrimitiveSet::Mode>(ps, "Mode")
		.value("POINTS", osg::PrimitiveSet::POINTS)
		.value("LINES", osg::PrimitiveSet::LINES)
		.value("LINE_STRIP", osg::PrimitiveSet::LINE_STRIP)
		.value("LINE_LOOP", osg::PrimitiveSet::LINE_LOOP)
		.value("TRIANGLES", osg::PrimitiveSet::TRIANGLES)
		.value("TRIANGLE_STRIP", osg::PrimitiveSet::TRIANGLE_STRIP)
		.value("TRIANGLE_FAN", osg::PrimitiveSet::TRIANGLE_FAN)
		.value("QUADS", osg::PrimitiveSet::QUADS)
		.value("QUAD_STRIP", osg::PrimitiveSet::QUAD_STRIP)
		.value("POLYGON", osg::PrimitiveSet::POLYGON)
		.value("LINES_ADJACENCY", osg::PrimitiveSet::LINES_ADJACENCY)
		.value("LINE_STRIP_ADJACENCY", osg::PrimitiveSet::LINE_STRIP_ADJACENCY)
		.value("TRIANGLES_ADJACENCY", osg::PrimitiveSet::TRIANGLES_ADJACENCY)
		.value("TRIANGLE_STRIP_ADJACENCY", osg::PrimitiveSet::TRIANGLE_STRIP_ADJACENCY)
		.value("PATCHES", osg::PrimitiveSet::PATCHES)
		.export_values()
	;

	ps
		.def_property(
			"numInstances",
			&osg::PrimitiveSet::getNumInstances,
			&osg::PrimitiveSet::setNumInstances
		)
		.def_property(
			"mode",
			&osg::PrimitiveSet::getMode,
			&osg::PrimitiveSet::setMode
		)
		.def_property_readonly("numIndices", &osg::PrimitiveSet::getNumIndices)
		// .def_property_readonly("numIndices", &detail::PrimitiveSet::getNumIndices)
		.def("index", &osg::PrimitiveSet::index)
		.def("offsetIndices", &osg::PrimitiveSet::offsetIndices)
		.def("draw", &osg::PrimitiveSet::draw)
		.def(
			"accept",
			py::overload_cast<osg::PrimitiveFunctor&>(&osg::PrimitiveSet::accept, py::const_)
		)
		.def(
			"accept",
			py::overload_cast<osg::PrimitiveIndexFunctor&>(&osg::PrimitiveSet::accept, py::const_)
		)
	;

	py::class_<osg::DrawArrays, osg::PrimitiveSet, osg::ref_ptr<osg::DrawArrays>>(m, "DrawArrays")
		.def(py::init<GLenum>(), "mode"_a=0)
		.def(py::init<GLenum, GLint, GLsizei, int>(),
			"mode"_a,
			"first"_a,
			"count"_a,
			"numInstances"_a=0
		)
		.def_property("first", &osg::DrawArrays::getFirst, &osg::DrawArrays::setFirst)
		.def_property("count", &osg::DrawArrays::getCount, &osg::DrawArrays::setCount)
	;

	// bool addPrimitiveSet(PrimitiveSet* primitiveset);
	// virtual void setUseVertexBufferObjects(bool flag);
	py::class_<osg::Geometry, osg::Drawable, osg::ref_ptr<osg::Geometry>>(m, "Geometry")
		.def(py::init<>())

		// Properties (new) alongside the old set*Array()/get*Array() method calls (kept for
		// compatibility -- osgGLTF's loader still calls setVertexArray()/setColorArray()
		// directly). Both forms share the same PropertySlot per array, so whichever one runs
		// last correctly evicts what the other cached.
		.def_property(
			"vertexArray",
			detail::GeometrySlots::getter<detail::VertexArraySlot>(
				static_cast<osg::Array*(osg::Geometry::*)()>(&osg::Geometry::getVertexArray)
			),
			detail::GeometrySlots::setter<detail::VertexArraySlot, osg::Array*>(
				&osg::Geometry::setVertexArray
			)
		)
		.def_property(
			"colorArray",
			detail::GeometrySlots::getter<detail::ColorArraySlot>(
				static_cast<osg::Array*(osg::Geometry::*)()>(&osg::Geometry::getColorArray)
			),
			detail::GeometrySlots::setter<detail::ColorArraySlot, osg::Array*>(
				py::overload_cast<osg::Array*>(&osg::Geometry::setColorArray)
			)
		)
		.def_property(
			"normalArray",
			detail::GeometrySlots::getter<detail::NormalArraySlot>(
				static_cast<osg::Array*(osg::Geometry::*)()>(&osg::Geometry::getNormalArray)
			),
			detail::GeometrySlots::setter<detail::NormalArraySlot, osg::Array*>(
				py::overload_cast<osg::Array*>(&osg::Geometry::setNormalArray)
			)
		)

		// void setVertexAttribArray(unsigned int index, Array* array) { setVertexAttribArray(index, array, osg::Array::BIND_UNDEFINED); }
		// void setVertexAttribArray(unsigned int index, Array* array, osg::Array::Binding binding);
		// void setVertexAttribBinding(unsigned int index,AttributeBinding ab);
		// void setVertexAttribNormalize(unsigned int index,GLboolean norm);
		// TODO: TexCoordArray should eventually be a pyx::MappingProxy (unit -> Array), like
		// StateSet.textureAttributes -- deferred, no rush.
		// TODO: TEMPORARY! (Until I can introduce my new SequenceProxy!
		.def(
			"addPrimitiveSet",
			&osg::Geometry::addPrimitiveSet,
			py::keep_alive<1, 2>()
		)
	;

	m
		.def(
			"createTexturedQuadGeometry",
			py::overload_cast<
				const osg::Vec3&,
				const osg::Vec3&,
				const osg::Vec3&,
				float,
				float,
				float,
				float
			>(&osg::createTexturedQuadGeometry)
		)
		.def(
			"createTexturedQuadGeometry",
			py::overload_cast<
				const osg::Vec3&,
				const osg::Vec3&,
				const osg::Vec3&,
				float,
				float
			>(&osg::createTexturedQuadGeometry),
			"corner"_a,
			"width"_a,
			"height"_a,
			"s"_a=1.0f,
			"t"_a=1.0f
		)
	;
}

}
