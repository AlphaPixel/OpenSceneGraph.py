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
	// reset()/update()/getValue()/getValueAt()/duration are all inherited Python-side from the
	// Motion base binding once it's registered as the base class here, no need to repeat them.
	template<typename T>
	void bind_Motion(py::module_& m, const char* name) {
		py::class_<T, osgAnimation::Motion, osg::ref_ptr<T>>(m, name)
			.def(py::init<float, float, float, osgAnimation::Motion::TimeBehaviour>(),
				"startValue"_a=0.0f,
				"duration"_a=1.0f,
				"changeValue"_a=1.0f,
				"timeBehaviour"_a=osgAnimation::Motion::CLAMP
			)
		;
	}
}

void bind(py::module_& m) {
	m.def("linear", detail::wrap(osgAnimation::LinearFunction::getValueAt), "t"_a);

	m.def("inQuad", detail::wrap(osgAnimation::InQuadFunction::getValueAt), "t"_a);
	m.def("outQuad", detail::wrap(osgAnimation::OutQuadFunction::getValueAt), "t"_a);
	m.def("inOutQuad", detail::wrap(osgAnimation::InOutQuadFunction::getValueAt), "t"_a);

	m.def("inCubic", detail::wrap(osgAnimation::InCubicFunction::getValueAt), "t"_a);
	m.def("outCubic", detail::wrap(osgAnimation::OutCubicFunction::getValueAt), "t"_a);
	m.def("inOutCubic", detail::wrap(osgAnimation::InOutCubicFunction::getValueAt), "t"_a);

	m.def("inQuart", detail::wrap(osgAnimation::InQuartFunction::getValueAt), "t"_a);
	m.def("outQuart", detail::wrap(osgAnimation::OutQuartFunction::getValueAt), "t"_a);
	m.def("inOutQuart", detail::wrap(osgAnimation::InOutQuartFunction::getValueAt), "t"_a);

	m.def("inBounce", detail::wrap(osgAnimation::InBounceFunction::getValueAt), "t"_a);
	m.def("outBounce", detail::wrap(osgAnimation::OutBounceFunction::getValueAt), "t"_a);
	m.def("inOutBounce", detail::wrap(osgAnimation::InOutBounceFunction::getValueAt), "t"_a);

	m.def("inElastic", detail::wrap(osgAnimation::InElasticFunction::getValueAt), "t"_a);
	m.def("outElastic", detail::wrap(osgAnimation::OutElasticFunction::getValueAt), "t"_a);
	m.def("inOutElastic", detail::wrap(osgAnimation::InOutElasticFunction::getValueAt), "t"_a);

	m.def("inSine", detail::wrap(osgAnimation::InSineFunction::getValueAt), "t"_a);
	m.def("outSine", detail::wrap(osgAnimation::OutSineFunction::getValueAt), "t"_a);
	m.def("inOutSine", detail::wrap(osgAnimation::InOutSineFunction::getValueAt), "t"_a);

	m.def("inBack", detail::wrap(osgAnimation::InBackFunction::getValueAt), "t"_a);
	m.def("outBack", detail::wrap(osgAnimation::OutBackFunction::getValueAt), "t"_a);
	m.def("inOutBack", detail::wrap(osgAnimation::InOutBackFunction::getValueAt), "t"_a);

	m.def("inCirc", detail::wrap(osgAnimation::InCircFunction::getValueAt), "t"_a);
	m.def("outCirc", detail::wrap(osgAnimation::OutCircFunction::getValueAt), "t"_a);
	m.def("inOutCirc", detail::wrap(osgAnimation::InOutCircFunction::getValueAt), "t"_a);

	m.def("inExpo", detail::wrap(osgAnimation::InExpoFunction::getValueAt), "t"_a);
	m.def("outExpo", detail::wrap(osgAnimation::OutExpoFunction::getValueAt), "t"_a);
	m.def("inOutExpo", detail::wrap(osgAnimation::InOutExpoFunction::getValueAt), "t"_a);

	// ============================================================================================
	// Motion - stateful drivers (reset()/update(dt)/getValue()) built on the same curves above.
	// ============================================================================================

	auto motion = py::class_<
		osgAnimation::Motion,
		osg::Referenced,
		osg::ref_ptr<osgAnimation::Motion>
	>(m, "Motion")
		.def("reset", &osgAnimation::Motion::reset)
		.def_property("time", &osgAnimation::Motion::getTime, &osgAnimation::Motion::setTime)
		.def("update", &osgAnimation::Motion::update, "dt"_a)
		.def("getValue", static_cast<
			osgAnimation::Motion::value_type (osgAnimation::Motion::*)() const
		>(&osgAnimation::Motion::getValue))
		.def("getValueAt", static_cast<
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
	// addMotion() is a thin wrapper around its MotionList (a plain std::vector<ref_ptr<Motion>>);
	// not exposing full list ergonomics (indexing/removal/iteration) here - append-only covers the
	// "sequence these curves" use case this was asked for.
	py::class_<
		osgAnimation::CompositeMotion,
		osgAnimation::Motion,
		osg::ref_ptr<osgAnimation::CompositeMotion>
	>(m, "CompositeMotion")
		.def(py::init<float, float, float, osgAnimation::Motion::TimeBehaviour>(),
			"startValue"_a=0.0f,
			"duration"_a=1.0f,
			"changeValue"_a=1.0f,
			"timeBehaviour"_a=osgAnimation::Motion::CLAMP
		)
		.def("addMotion", [](osgAnimation::CompositeMotion& self, osgAnimation::Motion* _motion) {
			self.getMotionList().push_back(_motion);
		}, "motion"_a)
	;
}

}
