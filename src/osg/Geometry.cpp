#include "../pyosg.hpp"

PYOSG_DISABLE_WARNINGS

#include <osg/Geometry>

PYOSG_ENABLE_WARNINGS

// TODO: PrimitiveSet

namespace pyosg {

namespace detail {
	/* template<>
	void kwargs_init(osg::Object& self, const py::kwargs& kwargs) {
		if(kwargs.contains("name")) self.setName(kwargs["name"].cast<std::string>());
	} */

	class PrimitiveSet: public osg::PrimitiveSet {
	public:
		using osg::PrimitiveSet::PrimitiveSet;

		void draw(osg::State& state, bool useVertexBufferObjects) const override {
			PYBIND11_OVERRIDE_PURE(
				void,
				osg::PrimitiveSet,
				draw,
				state,
				useVertexBufferObjects
			);
		}

		void accept(osg::PrimitiveFunctor& functor) const override {
			PYBIND11_OVERRIDE_PURE(
				void,
				osg::PrimitiveSet,
				accept,
				functor
			);
		}

		void accept(osg::PrimitiveIndexFunctor& functor) const override {
			PYBIND11_OVERRIDE_PURE(
				void,
				osg::PrimitiveSet,
				accept,
				functor
			);
		}

		unsigned int index(unsigned int pos) const override {
			PYBIND11_OVERRIDE_PURE(
				unsigned int,
				osg::PrimitiveSet,
				index,
				pos
			);
		}

		unsigned int getNumIndices() const override {
			PYBIND11_OVERRIDE_PURE(
				unsigned int,
				osg::PrimitiveSet,
				getNumIndices
			);
		}

		void offsetIndices(int offset) override {
			PYBIND11_OVERRIDE_PURE(
				void,
				osg::PrimitiveSet,
				offsetIndices,
				offset
			);
		}
	};
}

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
		// void setVertexArray(Array* array);
		.def(
			"setVertexArray",
			&osg::Geometry::setVertexArray,
			py::keep_alive<1, 2>()
		)
		.def(
			"setColorArray",
			py::overload_cast<osg::Array*>(&osg::Geometry::setColorArray),
			py::keep_alive<1, 2>()
		)
		.def(
			"setColorArray",
			py::overload_cast<osg::Array*, osg::Array::Binding>(&osg::Geometry::setColorArray),
			py::keep_alive<1, 2>()
		)
		// void setVertexAttribArray(unsigned int index, Array* array) { setVertexAttribArray(index, array, osg::Array::BIND_UNDEFINED); }
		// void setVertexAttribArray(unsigned int index, Array* array, osg::Array::Binding binding);
		// void setVertexAttribBinding(unsigned int index,AttributeBinding ab);
		// void setVertexAttribNormalize(unsigned int index,GLboolean norm);
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
