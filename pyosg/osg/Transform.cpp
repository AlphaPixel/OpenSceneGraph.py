#include "Transform.hpp"
// TODO: We include the following file ONLY BECAUSE we need the `MAKE_OPAQUE` call in the same
// source file where it's actually USED. :/ There are ways around this we can add to pybind11x.hpp
// at some time in the future.
#include "NodeVisitor.hpp"

namespace pybind11x {
	template<>
	void kwargs_init_own(osg::Transform& self, const py::kwargs& kwargs) {
		if(kwargs.contains("referenceFrame")) self.setReferenceFrame(
			kwargs["referenceFrame"].cast<osg::Transform::ReferenceFrame>()
		);
	}

	template<>
	void kwargs_init_own(osg::MatrixTransform& self, const py::kwargs& kwargs) {
		if(kwargs.contains("matrix")) self.setMatrix(kwargs["matrix"].cast<osg::Matrix>());
	}

	template<>
	void kwargs_init_own(osg::PositionAttitudeTransform& self, const py::kwargs& kwargs) {
		// `setPosition`/`setScale`/`setPivotPoint` all take `const osg::Vec3d&` explicitly (not
		// the generic `osg::Vec3` = `Vec3f` alias) -- matching that here, not just what happens
		// to compile, since `.position`/`.scale`/`.pivotPoint` getters return `Vec3d` too and a
		// `Vec3f` cast silently truncates precision instead of matching them.
		if(kwargs.contains("position")) self.setPosition(kwargs["position"].cast<osg::Vec3d>());
		if(kwargs.contains("scale")) self.setScale(kwargs["scale"].cast<osg::Vec3d>());
		if(kwargs.contains("pivotPoint")) self.setPivotPoint(kwargs["pivotPoint"].cast<osg::Vec3d>());
	}
}

namespace pyosg {

void bind_Transform(py::module_& m) {
	auto transform = py::class_<
		osg::Transform,
		osg::Group,
		osg::ref_ptr<osg::Transform>
	>(m, "Transform")
		.def(py::init<>())
		.def(py::init(pyx::kwargs_ctor<osg::Transform>()))
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
		.def(py::init(pyx::kwargs_ctor<osg::MatrixTransform>()))
		.def(py::init(pyx::kwargs_ctor<osg::MatrixTransform, const osg::Matrix&>()))
		.def_property(
			"matrix",
			py::cpp_function(
				&osg::MatrixTransform::getMatrix,
				py::return_value_policy::reference_internal
			),
			&osg::MatrixTransform::setMatrix,
			"Live reference to the transform's native matrix. "
			"Use osg.Matrix(transform.matrix) when retaining a value snapshot."
		)
	;

	py::class_<
		osg::PositionAttitudeTransform,
		osg::Transform,
		osg::ref_ptr<osg::PositionAttitudeTransform>
	>(m, "PositionAttitudeTransform")
		.def(py::init<>())
		.def(py::init<const osg::PositionAttitudeTransform&>())
		.def(py::init(pyx::kwargs_ctor<osg::PositionAttitudeTransform>()))
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
