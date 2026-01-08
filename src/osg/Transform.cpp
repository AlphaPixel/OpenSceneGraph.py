#include "../pyosg.hpp"

PYOSG_DISABLE_WARNINGS

#include <osg/MatrixTransform>
#include <osg/PositionAttitudeTransform>

PYOSG_ENABLE_WARNINGS

namespace pyosg {

// namespace detail {}

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
}

}
