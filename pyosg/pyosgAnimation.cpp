#include "pyosgAnimation.hpp"

OSGX_DISABLE_WARNINGS

#include <osgAnimation/EaseMotion>

OSGX_ENABLE_WARNINGS

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
	m.def("linear", detail::wrap(osgAnimation::LinearFunction::getValueAt), "t"_a,
		"Evaluate the linear easing curve at normalized time t."
	);

	m.def("inQuad", detail::wrap(osgAnimation::InQuadFunction::getValueAt), "t"_a,
		"Evaluate the quadratic ease-in curve at normalized time t."
	);
	m.def("outQuad", detail::wrap(osgAnimation::OutQuadFunction::getValueAt), "t"_a,
		"Evaluate the quadratic ease-out curve at normalized time t."
	);
	m.def("inOutQuad", detail::wrap(osgAnimation::InOutQuadFunction::getValueAt), "t"_a,
		"Evaluate the quadratic ease-in-out curve at normalized time t."
	);

	m.def("inCubic", detail::wrap(osgAnimation::InCubicFunction::getValueAt), "t"_a,
		"Evaluate the cubic ease-in curve at normalized time t."
	);
	m.def("outCubic", detail::wrap(osgAnimation::OutCubicFunction::getValueAt), "t"_a,
		"Evaluate the cubic ease-out curve at normalized time t."
	);
	m.def("inOutCubic", detail::wrap(osgAnimation::InOutCubicFunction::getValueAt), "t"_a,
		"Evaluate the cubic ease-in-out curve at normalized time t."
	);

	m.def("inQuart", detail::wrap(osgAnimation::InQuartFunction::getValueAt), "t"_a,
		"Evaluate the quartic ease-in curve at normalized time t."
	);
	m.def("outQuart", detail::wrap(osgAnimation::OutQuartFunction::getValueAt), "t"_a,
		"Evaluate the quartic ease-out curve at normalized time t."
	);
	m.def("inOutQuart", detail::wrap(osgAnimation::InOutQuartFunction::getValueAt), "t"_a,
		"Evaluate the quartic ease-in-out curve at normalized time t."
	);

	m.def("inBounce", detail::wrap(osgAnimation::InBounceFunction::getValueAt), "t"_a,
		"Evaluate the bouncing ease-in curve at normalized time t."
	);
	m.def("outBounce", detail::wrap(osgAnimation::OutBounceFunction::getValueAt), "t"_a,
		"Evaluate the bouncing ease-out curve at normalized time t."
	);
	m.def("inOutBounce", detail::wrap(osgAnimation::InOutBounceFunction::getValueAt), "t"_a,
		"Evaluate the bouncing ease-in-out curve at normalized time t."
	);

	m.def("inElastic", detail::wrap(osgAnimation::InElasticFunction::getValueAt), "t"_a,
		"Evaluate the elastic ease-in curve at normalized time t."
	);
	m.def("outElastic", detail::wrap(osgAnimation::OutElasticFunction::getValueAt), "t"_a,
		"Evaluate the elastic ease-out curve at normalized time t."
	);
	m.def("inOutElastic", detail::wrap(osgAnimation::InOutElasticFunction::getValueAt), "t"_a,
		"Evaluate the elastic ease-in-out curve at normalized time t."
	);

	m.def("inSine", detail::wrap(osgAnimation::InSineFunction::getValueAt), "t"_a,
		"Evaluate the sinusoidal ease-in curve at normalized time t."
	);
	m.def("outSine", detail::wrap(osgAnimation::OutSineFunction::getValueAt), "t"_a,
		"Evaluate the sinusoidal ease-out curve at normalized time t."
	);
	m.def("inOutSine", detail::wrap(osgAnimation::InOutSineFunction::getValueAt), "t"_a,
		"Evaluate the sinusoidal ease-in-out curve at normalized time t."
	);

	m.def("inBack", detail::wrap(osgAnimation::InBackFunction::getValueAt), "t"_a,
		"Evaluate the overshooting ease-in curve at normalized time t."
	);
	m.def("outBack", detail::wrap(osgAnimation::OutBackFunction::getValueAt), "t"_a,
		"Evaluate the overshooting ease-out curve at normalized time t."
	);
	m.def("inOutBack", detail::wrap(osgAnimation::InOutBackFunction::getValueAt), "t"_a,
		"Evaluate the overshooting ease-in-out curve at normalized time t."
	);

	m.def("inCirc", detail::wrap(osgAnimation::InCircFunction::getValueAt), "t"_a,
		"Evaluate the circular ease-in curve at normalized time t."
	);
	m.def("outCirc", detail::wrap(osgAnimation::OutCircFunction::getValueAt), "t"_a,
		"Evaluate the circular ease-out curve at normalized time t."
	);
	m.def("inOutCirc", detail::wrap(osgAnimation::InOutCircFunction::getValueAt), "t"_a,
		"Evaluate the circular ease-in-out curve at normalized time t."
	);

	m.def("inExpo", detail::wrap(osgAnimation::InExpoFunction::getValueAt), "t"_a,
		"Evaluate the exponential ease-in curve at normalized time t."
	);
	m.def("outExpo", detail::wrap(osgAnimation::OutExpoFunction::getValueAt), "t"_a,
		"Evaluate the exponential ease-out curve at normalized time t."
	);
	m.def("inOutExpo", detail::wrap(osgAnimation::InOutExpoFunction::getValueAt), "t"_a,
		"Evaluate the exponential ease-in-out curve at normalized time t."
	);

	// ============================================================================================
	// Motion - stateful drivers (reset()/update(dt)/getValue()) built on the same curves above.
	// ============================================================================================

	auto motion = py::class_<
		osgAnimation::Motion,
		osg::Referenced,
		osg::ref_ptr<osgAnimation::Motion>
	>(
		m,
		"Motion",
		"Base class for a stateful animation driver (reset()/update(dt)/getValue()) built on "
		"one of the easing curve functions (linear, inQuad, outBounce, etc.)."
	)
		.def("reset", &osgAnimation::Motion::reset,
			"Reset the motion to its initial time and value."
		)
		.def_property("time", &osgAnimation::Motion::getTime, &osgAnimation::Motion::setTime,
			"The elapsed time in seconds since the motion was reset."
		)
		.def("update", &osgAnimation::Motion::update, "dt"_a,
			"Advance the motion by dt seconds."
		)
		.def("getValue", static_cast<
			osgAnimation::Motion::value_type (osgAnimation::Motion::*)() const
		>(&osgAnimation::Motion::getValue),
			"Return the motion's value at its current time."
		)
		.def("getValueAt", static_cast<
			osgAnimation::Motion::value_type (osgAnimation::Motion::*)(float) const
		>(&osgAnimation::Motion::getValueAt), "time"_a,
			"Return the motion's value at the supplied time in seconds."
		)
		.def_property_readonly("duration", &osgAnimation::Motion::getDuration,
			"The motion's duration in seconds."
		)
	;

	py::enum_<osgAnimation::Motion::TimeBehaviour>(motion, "TimeBehaviour",
		"Choose whether motion time clamps or loops at its duration."
	)
		.value("CLAMP", osgAnimation::Motion::CLAMP)
		.value("LOOP", osgAnimation::Motion::LOOP)
		.export_values()
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
	>(
		m,
		"CompositeMotion",
		"A Motion that sequences a list of child Motions end-to-end via addMotion()."
	)
		.def(py::init<float, float, float, osgAnimation::Motion::TimeBehaviour>(),
			"startValue"_a=0.0f,
			"duration"_a=1.0f,
			"changeValue"_a=1.0f,
			"timeBehaviour"_a=osgAnimation::Motion::CLAMP,
			"Create a composite motion with the given value range and timing behavior."
		)
		.def("addMotion", [](osgAnimation::CompositeMotion& self, osgAnimation::Motion* _motion) {
			self.getMotionList().push_back(_motion);
		}, "motion"_a,
			"Append a child motion to this sequence."
		)
	;
}

}
