#include "Geometry.hpp"

namespace pybind11x {
	template<>
	void kwargs_init_own(osg::Geometry& self, const py::kwargs& kwargs) {
		if(kwargs.contains("vertexArray")) {
			pyosg::detail::GeometrySlots::setter<pyosg::detail::VertexArraySlot, osg::Array*>(
				&osg::Geometry::setVertexArray
			)(self, kwargs["vertexArray"]);
		}

		if(kwargs.contains("colorArray")) {
			pyosg::detail::GeometrySlots::setter<pyosg::detail::ColorArraySlot, osg::Array*>(
				py::overload_cast<osg::Array*>(&osg::Geometry::setColorArray)
			)(self, kwargs["colorArray"]);
		}

		if(kwargs.contains("normalArray")) {
			pyosg::detail::GeometrySlots::setter<pyosg::detail::NormalArraySlot, osg::Array*>(
				py::overload_cast<osg::Array*>(&osg::Geometry::setNormalArray)
			)(self, kwargs["normalArray"]);
		}

		if(kwargs.contains("primitiveSets")) {
			for(py::handle ps : kwargs["primitiveSets"]) {
				self.addPrimitiveSet(ps.cast<osg::PrimitiveSet*>());
			}
		}
	}
}

namespace pyosg {

void bind_Geometry(py::module_& m) {
	py::class_<osg::PrimitiveFunctor>(
		m,
		"PrimitiveFunctor",
		"Visitor interface for iterating over a Geometry's vertex data resolved to raw "
		"primitives (triangles, lines, points)."
	);
	py::class_<osg::PrimitiveIndexFunctor>(
		m,
		"PrimitiveIndexFunctor",
		"Like PrimitiveFunctor, but visits vertex indices rather than resolved vertex values."
	);

	auto ps = py::class_<
		osg::PrimitiveSet,
		detail::PrimitiveSet,
		osg::BufferData,
		osg::ref_ptr<osg::PrimitiveSet>
	>(
		m,
		"PrimitiveSet",
		"Base class describing how a Geometry's vertex arrays are assembled into primitives "
		"(draw mode, vertex count/order)."
	);

	py::enum_<osg::PrimitiveSet::Type>(ps, "Type",
		"Which concrete PrimitiveSet subclass (and underlying draw call, e.g. DrawArrays vs. "
		"a DrawElements* variant) a set was built as."
	)
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

	py::enum_<osg::PrimitiveSet::Mode>(ps, "Mode",
		"OpenGL primitive topology this set's indices/vertices are drawn as, e.g. TRIANGLES "
		"or LINE_STRIP - matches the GL_* draw-mode constants."
	)
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
			&osg::PrimitiveSet::setNumInstances,
			"Number of instanced copies drawn via glDraw*Instanced; 0 (the OSG default) means "
			"non-instanced, a single draw."
		)
		.def_property(
			"mode",
			&osg::PrimitiveSet::getMode,
			&osg::PrimitiveSet::setMode,
			"The set's PrimitiveSet.Mode draw topology (e.g. TRIANGLES)."
		)
		.def_property_readonly("numIndices", &osg::PrimitiveSet::getNumIndices,
			"Number of vertex indices this set will draw."
		)
		// .def_property_readonly("numIndices", &detail::PrimitiveSet::getNumIndices)
		.def("index", &osg::PrimitiveSet::index,
			"Return the vertex-array index stored at position `pos` within this set."
		)
		.def("offsetIndices", &osg::PrimitiveSet::offsetIndices,
			"Add `offset` to every index in this set in place, e.g. when merging geometries "
			"that share one combined vertex array."
		)
		.def("draw", &osg::PrimitiveSet::draw,
			"Issue this set's raw glDrawArrays/glDrawElements call against the currently "
			"bound GL state; normally invoked internally by Geometry, not called directly."
		)
		.def(
			"accept",
			py::overload_cast<osg::PrimitiveFunctor&>(&osg::PrimitiveSet::accept, py::const_),
			"Visit this set's primitives resolved to actual vertex values via a PrimitiveFunctor."
		)
		.def(
			"accept",
			py::overload_cast<osg::PrimitiveIndexFunctor&>(&osg::PrimitiveSet::accept, py::const_),
			"Visit this set's primitives as raw vertex indices via a PrimitiveIndexFunctor."
		)
	;

	py::class_<osg::DrawArrays, osg::PrimitiveSet, osg::ref_ptr<osg::DrawArrays>>(
		m,
		"DrawArrays",
		"A PrimitiveSet that draws a contiguous run of vertices starting at a given index."
	)
		.def(py::init<GLenum>(), "mode"_a=0, "Create an empty DrawArrays with the given draw mode.")
		.def(py::init<GLenum, GLint, GLsizei, int>(),
			"mode"_a,
			"first"_a,
			"count"_a,
			"numInstances"_a=0,
			"Create a DrawArrays spanning `count` vertices starting at index `first`, drawn "
			"with the given mode."
		)
		.def_property("first", &osg::DrawArrays::getFirst, &osg::DrawArrays::setFirst,
			"Index of the first vertex to draw."
		)
		.def_property("count", &osg::DrawArrays::getCount, &osg::DrawArrays::setCount,
			"Number of contiguous vertices to draw starting at `first`."
		)
	;

	// virtual void setUseVertexBufferObjects(bool flag);
	auto geom = py::class_<osg::Geometry, osg::Drawable, osg::ref_ptr<osg::Geometry>>(
		m,
		"Geometry",
		"A Drawable built from vertex/color/normal arrays plus one or more PrimitiveSets "
		"describing how to draw them. .vertexArray/.colorArray/.normalArray are settable "
		"properties (alongside the traditional set*Array() methods), and .primitiveSets/"
		".vertexAttrib are sequence/mapping proxies rather than add/get method pairs."
	)
		.def(py::init<>(), "Create an empty Geometry with no arrays or primitive sets.")
		.def(py::init(pyx::kwargs_ctor<osg::Geometry>()),
			"Create a Geometry, optionally setting vertexArray/colorArray/normalArray/"
			"primitiveSets via keyword arguments."
		)

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
			),
			"The Array of per-vertex positions. To update an existing geometry, mutate this "
			"array's elements in place and call its .dirty() rather than reassigning a new "
			"Array every frame; a fresh Array is a brand-new GPU buffer allocation."
		)
		.def_property(
			"colorArray",
			detail::GeometrySlots::getter<detail::ColorArraySlot>(
				static_cast<osg::Array*(osg::Geometry::*)()>(&osg::Geometry::getColorArray)
			),
			detail::GeometrySlots::setter<detail::ColorArraySlot, osg::Array*>(
				py::overload_cast<osg::Array*>(&osg::Geometry::setColorArray)
			),
			"The Array of per-vertex (or per-primitive, depending on its .binding) color "
			"values; same in-place-mutate-plus-.dirty() rule as vertexArray."
		)
		.def_property(
			"normalArray",
			detail::GeometrySlots::getter<detail::NormalArraySlot>(
				static_cast<osg::Array*(osg::Geometry::*)()>(&osg::Geometry::getNormalArray)
			),
			detail::GeometrySlots::setter<detail::NormalArraySlot, osg::Array*>(
				py::overload_cast<osg::Array*>(&osg::Geometry::setNormalArray)
			),
			"The Array of per-vertex (or per-primitive, depending on its .binding) normal "
			"vectors; same in-place-mutate-plus-.dirty() rule as vertexArray."
		)

		// TODO: TexCoordArray should eventually be a pyx::MappingProxy (unit -> Array), like
		// StateSet.textureAttributes -- deferred, no rush.

		// No addPrimitiveSet() method binding -- use `.primitiveSets.append(...)` below (the old
		// method form was removed once the SequenceProxy existed, forcing every call site to
		// port forward rather than accumulating a second permanent form; unlike vertexArray/
		// colorArray/normalArray's dual forms above, nothing outside this repo's own Python
		// examples called it -- osgGLTF's C++ loader calls osg::Geometry::addPrimitiveSet()
		// directly, not through this binding).
	;

	pyx::bind_proxy_property<detail::VertexAttribProxy, osg::Geometry, detail::GeometryStorage>(
		geom, "_VertexAttrib", "vertexAttrib",
		"Mapping proxy of generic vertex-attribute index -> Array (setVertexAttribArray's "
		"index slot, e.g. for a shader's manually-bound osg_Tangent). Assigning `geom."
		"vertexAttrib[i] = arr` replaces the array at that index; deleting a key clears it."
	);
	pyx::bind_proxy_property<detail::PrimitiveSetsProxy, osg::Geometry, detail::GeometryStorage>(
		geom, "_PrimitiveSets", "primitiveSets",
		"Sequence proxy over this Geometry's PrimitiveSets - supports indexing, `len()`, "
		"`.append()`, `.insert()`, and `del` in place of add/removePrimitiveSet()."
	);

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
			>(&osg::createTexturedQuadGeometry),
			"Build a single-quad Geometry from a corner point and two edge vectors, with an "
			"explicit texture-coordinate rectangle (l, b, r, t)."
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
			"t"_a=1.0f,
			"Build a single-quad Geometry from a corner point and width/height edge vectors, "
			"with texture coordinates spanning (0, 0) to (s, t)."
		)
	;
}

}
