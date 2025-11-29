#include "../osg.hpp"

PYOSG_DISABLE_WARNINGS

#include <osg/State>

PYOSG_ENABLE_WARNINGS

namespace pyosg {

// namespace detail {}

void bind_State(py::module_& m) {
	py::class_<osg::FrameStamp, osg::Referenced, osg::ref_ptr<osg::FrameStamp>>(m, "FrameStamp")
		.def(py::init<>())
		.def(py::init<const osg::FrameStamp&>())
		.def_property("frameNumber",
			&osg::FrameStamp::getFrameNumber,
			&osg::FrameStamp::setFrameNumber
		)
		.def_property("referenceTime",
			&osg::FrameStamp::getReferenceTime,
			&osg::FrameStamp::setReferenceTime
		)
		.def_property("simulationTime",
			&osg::FrameStamp::getSimulationTime,
			&osg::FrameStamp::setSimulationTime
		)
		.def_property("calendarTime",
			&osg::FrameStamp::getCalendarTime,
			&osg::FrameStamp::setCalendarTime
		)
	;

	py::class_<osg::State, osg::Referenced, osg::ref_ptr<osg::State>>(m, "State")
		.def_property_readonly("contextID", &osg::State::getContextID)
		/* .def("getGraphicsContext",
			&osg::State::getGraphicsContext,
			py::return_value_policy::reference
		) */
		.def_property_readonly("frameStamp",
			py::overload_cast<>(&osg::State::getFrameStamp, py::const_),
			py::return_value_policy::reference
		)
		/* .def("setUseModelViewAndProjectionUniforms",
			&osg::State::setUseModelViewAndProjectionUniforms
		)
		.def("setUseVertexAttributeAliasing",
			&osg::State::setUseVertexAttributeAliasing
		)
		.def("checkGLErrors",
			py::overload_cast<const char*>(&osg::State::checkGLErrors)
		) */
	;
}

}
