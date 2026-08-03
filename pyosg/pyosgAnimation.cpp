#include "pyosgAnimation.hpp"

PYOSG_DISABLE_WARNINGS

#include <osgAnimation/EaseMotion>

PYOSG_ENABLE_WARNINGS

namespace pyosgAnimation {

namespace detail {

// osgAnimation::EaseMotion's curve structs all expose a static
// `getValueAt(float t, float& result)`; adapt that shape into a plain (t) -> value
// Python-callable rather than binding each struct as its own type.
template<typename Fn>
auto wrap(Fn fn) {
	return [fn](float t) {
		float result = 0.0f;

		fn(t, result);

		return result;
	};
}

// Every osgAnimation::XxxMotion is a distinct C++ type (a MathMotionTemplate<XxxFunction>
// instantiation), so each needs its own py::class_ - but only the constructor differs per type;
// reset()/update()/get_value()/get_value_at()/duration are all inherited Python-side from the
// Motion base binding once it's registered as the base class here, no need to repeat them.
template<typename T>
void bind_Motion(py::module_& m, const char* name) {
	py::class_<T, osgAnimation::Motion, osg::ref_ptr<T>>(m, name)
		.def(py::init<float, float, float, osgAnimation::Motion::TimeBehaviour>(),
			"start_value"_a=0.0f,
			"duration"_a=1.0f,
			"change_value"_a=1.0f,
			"time_behaviour"_a=osgAnimation::Motion::CLAMP
		)
	;
}

}

void bind(py::module_& m) {
	m.def("linear", detail::wrap(osgAnimation::LinearFunction::getValueAt), "t"_a);

	m.def("in_quad", detail::wrap(osgAnimation::InQuadFunction::getValueAt), "t"_a);
	m.def("out_quad", detail::wrap(osgAnimation::OutQuadFunction::getValueAt), "t"_a);
	m.def("in_out_quad", detail::wrap(osgAnimation::InOutQuadFunction::getValueAt), "t"_a);

	m.def("in_cubic", detail::wrap(osgAnimation::InCubicFunction::getValueAt), "t"_a);
	m.def("out_cubic", detail::wrap(osgAnimation::OutCubicFunction::getValueAt), "t"_a);
	m.def("in_out_cubic", detail::wrap(osgAnimation::InOutCubicFunction::getValueAt), "t"_a);

	m.def("in_quart", detail::wrap(osgAnimation::InQuartFunction::getValueAt), "t"_a);
	m.def("out_quart", detail::wrap(osgAnimation::OutQuartFunction::getValueAt), "t"_a);
	m.def("in_out_quart", detail::wrap(osgAnimation::InOutQuartFunction::getValueAt), "t"_a);

	m.def("in_bounce", detail::wrap(osgAnimation::InBounceFunction::getValueAt), "t"_a);
	m.def("out_bounce", detail::wrap(osgAnimation::OutBounceFunction::getValueAt), "t"_a);
	m.def("in_out_bounce", detail::wrap(osgAnimation::InOutBounceFunction::getValueAt), "t"_a);

	m.def("in_elastic", detail::wrap(osgAnimation::InElasticFunction::getValueAt), "t"_a);
	m.def("out_elastic", detail::wrap(osgAnimation::OutElasticFunction::getValueAt), "t"_a);
	m.def("in_out_elastic", detail::wrap(osgAnimation::InOutElasticFunction::getValueAt), "t"_a);

	m.def("in_sine", detail::wrap(osgAnimation::InSineFunction::getValueAt), "t"_a);
	m.def("out_sine", detail::wrap(osgAnimation::OutSineFunction::getValueAt), "t"_a);
	m.def("in_out_sine", detail::wrap(osgAnimation::InOutSineFunction::getValueAt), "t"_a);

	m.def("in_back", detail::wrap(osgAnimation::InBackFunction::getValueAt), "t"_a);
	m.def("out_back", detail::wrap(osgAnimation::OutBackFunction::getValueAt), "t"_a);
	m.def("in_out_back", detail::wrap(osgAnimation::InOutBackFunction::getValueAt), "t"_a);

	m.def("in_circ", detail::wrap(osgAnimation::InCircFunction::getValueAt), "t"_a);
	m.def("out_circ", detail::wrap(osgAnimation::OutCircFunction::getValueAt), "t"_a);
	m.def("in_out_circ", detail::wrap(osgAnimation::InOutCircFunction::getValueAt), "t"_a);

	m.def("in_expo", detail::wrap(osgAnimation::InExpoFunction::getValueAt), "t"_a);
	m.def("out_expo", detail::wrap(osgAnimation::OutExpoFunction::getValueAt), "t"_a);
	m.def("in_out_expo", detail::wrap(osgAnimation::InOutExpoFunction::getValueAt), "t"_a);

	// ============================================================================================
	// Motion - stateful drivers (reset()/update(dt)/get_value()) built on the same curves above.
	// ============================================================================================

	auto motion = py::class_<
		osgAnimation::Motion,
		osg::Referenced,
		osg::ref_ptr<osgAnimation::Motion>
	>(m, "Motion")
		.def("reset", &osgAnimation::Motion::reset)
		.def_property("time", &osgAnimation::Motion::getTime, &osgAnimation::Motion::setTime)
		.def("update", &osgAnimation::Motion::update, "dt"_a)
		.def("get_value", static_cast<
			osgAnimation::Motion::value_type (osgAnimation::Motion::*)() const
		>(&osgAnimation::Motion::getValue))
		.def("get_value_at", static_cast<
			osgAnimation::Motion::value_type (osgAnimation::Motion::*)(float) const
		>(&osgAnimation::Motion::getValueAt), "time"_a)
		.def_property_readonly("duration", &osgAnimation::Motion::getDuration)
	;

	py::enum_<osgAnimation::Motion::TimeBehaviour>(motion, "TimeBehaviour")
		.value("CLAMP", osgAnimation::Motion::CLAMP)
		.value("LOOP", osgAnimation::Motion::LOOP)
	;

	detail::bind_Motion<osgAnimation::LinearMotion>(m, "LinearMotion");

	detail::bind_Motion<osgAnimation::InQuadMotion>(m, "InQuadMotion");
	detail::bind_Motion<osgAnimation::OutQuadMotion>(m, "OutQuadMotion");
	detail::bind_Motion<osgAnimation::InOutQuadMotion>(m, "InOutQuadMotion");

	detail::bind_Motion<osgAnimation::InCubicMotion>(m, "InCubicMotion");
	detail::bind_Motion<osgAnimation::OutCubicMotion>(m, "OutCubicMotion");
	detail::bind_Motion<osgAnimation::InOutCubicMotion>(m, "InOutCubicMotion");

	detail::bind_Motion<osgAnimation::InQuartMotion>(m, "InQuartMotion");
	detail::bind_Motion<osgAnimation::OutQuartMotion>(m, "OutQuartMotion");
	detail::bind_Motion<osgAnimation::InOutQuartMotion>(m, "InOutQuartMotion");

	detail::bind_Motion<osgAnimation::InBounceMotion>(m, "InBounceMotion");
	detail::bind_Motion<osgAnimation::OutBounceMotion>(m, "OutBounceMotion");
	detail::bind_Motion<osgAnimation::InOutBounceMotion>(m, "InOutBounceMotion");

	detail::bind_Motion<osgAnimation::InElasticMotion>(m, "InElasticMotion");
	detail::bind_Motion<osgAnimation::OutElasticMotion>(m, "OutElasticMotion");
	detail::bind_Motion<osgAnimation::InOutElasticMotion>(m, "InOutElasticMotion");

	detail::bind_Motion<osgAnimation::InSineMotion>(m, "InSineMotion");
	detail::bind_Motion<osgAnimation::OutSineMotion>(m, "OutSineMotion");
	detail::bind_Motion<osgAnimation::InOutSineMotion>(m, "InOutSineMotion");

	detail::bind_Motion<osgAnimation::InBackMotion>(m, "InBackMotion");
	detail::bind_Motion<osgAnimation::OutBackMotion>(m, "OutBackMotion");
	detail::bind_Motion<osgAnimation::InOutBackMotion>(m, "InOutBackMotion");

	detail::bind_Motion<osgAnimation::InCircMotion>(m, "InCircMotion");
	detail::bind_Motion<osgAnimation::OutCircMotion>(m, "OutCircMotion");
	detail::bind_Motion<osgAnimation::InOutCircMotion>(m, "InOutCircMotion");

	detail::bind_Motion<osgAnimation::InExpoMotion>(m, "InExpoMotion");
	detail::bind_Motion<osgAnimation::OutExpoMotion>(m, "OutExpoMotion");
	detail::bind_Motion<osgAnimation::InOutExpoMotion>(m, "InOutExpoMotion");

	// CompositeMotion is concrete (not a MathMotionTemplate<> instantiation) and sequences a list
	// of child Motions end-to-end - see osgAnimation::CompositeMotion::getValueInNormalizedRange.
	// add_motion() is a thin wrapper around its MotionList (a plain std::vector<ref_ptr<Motion>>);
	// not exposing full list ergonomics (indexing/removal/iteration) here - append-only covers the
	// "sequence these curves" use case this was asked for.
	py::class_<
		osgAnimation::CompositeMotion,
		osgAnimation::Motion,
		osg::ref_ptr<osgAnimation::CompositeMotion>
	>(m, "CompositeMotion")
		.def(py::init<float, float, float, osgAnimation::Motion::TimeBehaviour>(),
			"start_value"_a=0.0f,
			"duration"_a=1.0f,
			"change_value"_a=1.0f,
			"time_behaviour"_a=osgAnimation::Motion::CLAMP
		)
		.def("add_motion", [](osgAnimation::CompositeMotion& self, osgAnimation::Motion* _motion) {
			self.getMotionList().push_back(_motion);
		}, "motion"_a)
	;
}

}
