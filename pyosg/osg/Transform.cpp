#include "Transform.hpp"
// TODO: We include the following file ONLY BECAUSE we need the `MAKE_OPAQUE` call in the same
// source file where it's actually USED. :/ There are ways around this we can add to pybind11x.hpp
// at some time in the future.
#include "NodeVisitor.hpp"

namespace pyosg {

void bind_Transform(py::module_& m) {
	auto transform = py::class_<
		osg::Transform,
		osg::Group,
		osg::ref_ptr<osg::Transform>
	>(m, "Transform")
		.def(py::init<>())
	;

	py::enum_<osg::Transform::ReferenceFrame>(transform, "ReferenceFrame")
		.value("RELATIVE_RF", osg::Transform::RELATIVE_RF)
		.value("ABSOLUTE_RF", osg::Transform::ABSOLUTE_RF)
		.value("ABSOLUTE_RF_INHERIT_VIEWPOINT", osg::Transform::ABSOLUTE_RF_INHERIT_VIEWPOINT)
		.export_values()
	;

	py::class_<
		osg::MatrixTransform,
		osg::Transform,
		osg::ref_ptr<osg::MatrixTransform>
	>(m, "MatrixTransform")
		.def(py::init<>())
		.def(py::init<const osg::Matrix&>())
		.def(py::init<const osg::MatrixTransform&>())
		.def_property(
			"matrix",
			&osg::MatrixTransform::getMatrix,
			&osg::MatrixTransform::setMatrix
		)
	;

	py::class_<
		osg::PositionAttitudeTransform,
		osg::Transform,
		osg::ref_ptr<osg::PositionAttitudeTransform>
	>(m, "PositionAttitudeTransform")
		.def(py::init<>())
		.def(py::init<const osg::PositionAttitudeTransform&>())
		.def_property(
			"position",
			&osg::PositionAttitudeTransform::getPosition,
			&osg::PositionAttitudeTransform::setPosition
		)
		// TODO: Implement `osg::Quat` wrapper!
		/* .def_property(
			"attitude",
			&osg::PositionAttitudeTransform::getAttitude,
			&osg::PositionAttitudeTransform::setAttitude
		) */
		.def_property(
			"scale",
			&osg::PositionAttitudeTransform::getScale,
			&osg::PositionAttitudeTransform::setScale
		)
		.def_property(
			"pivotPoint",
			&osg::PositionAttitudeTransform::getPivotPoint,
			&osg::PositionAttitudeTransform::setPivotPoint
		)
	;

	transform
		.def_property(
			"referenceFrame",
			&osg::Transform::getReferenceFrame,
			&osg::Transform::setReferenceFrame
		)
		.def(
			"asMatrixTransform",
			py::overload_cast<>(&osg::Transform::asMatrixTransform),
			py::return_value_policy::reference_internal
		)
		.def(
			"asPositionAttitudeTransform",
			py::overload_cast<>(&osg::Transform::asPositionAttitudeTransform),
			py::return_value_policy::reference_internal
		)
	;

	m
		.def("computeLocalToWorld", &osg::computeLocalToWorld,
			"nodePath"_a,
			"ignoreCameras"_a=true
		)
		.def("computeWorldToLocal", &osg::computeWorldToLocal,
			"nodePath"_a,
			"ignoreCameras"_a=true
		)
		.def("computeLocalToEye", &osg::computeLocalToEye,
			"modelview"_a,
			"nodePath"_a,
			"ignoreCameras"_a=true
		)
		.def("computeEyeToLocal", &osg::computeEyeToLocal,
			"modelview"_a,
			"nodePath"_a,
			"ignoreCameras"_a=true
		)
	;
}

}
