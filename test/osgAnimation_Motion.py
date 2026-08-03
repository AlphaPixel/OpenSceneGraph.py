#vimrun! pytest -sv ../test/osgAnimation_Motion.py

import pytest

from OpenSceneGraph import osgAnimation
from OpenSceneGraph.osgAnimation import CompositeMotion, LinearMotion, Motion

def test_easing_functions_bound():
	assert osgAnimation.linear(0.0) == pytest.approx(0.0)
	assert osgAnimation.linear(1.0) == pytest.approx(1.0)
	assert osgAnimation.out_bounce(1.0) == pytest.approx(1.0)

def test_motion_base_not_constructible():
	# Motion has a pure-virtual getValueInNormalizedRange() and is only bound as a base for the
	# concrete XxxMotion typedefs (LinearMotion, InOutCubicMotion, etc.) -- no py::init<>(), so
	# Python can't instantiate it directly.
	with pytest.raises(TypeError):
		Motion()

def test_linear_motion_update_and_value():
	m = LinearMotion(start_value=0.0, duration=1.0, change_value=1.0)

	assert m.get_value() == pytest.approx(0.0)

	m.update(0.5)

	assert m.get_value() == pytest.approx(0.5)

	m.update(0.5)

	assert m.get_value() == pytest.approx(1.0)

def test_linear_motion_reset():
	m = LinearMotion(start_value=0.0, duration=1.0, change_value=1.0)

	m.update(0.5)

	assert m.get_value() == pytest.approx(0.5)

	m.reset()

	assert m.get_value() == pytest.approx(0.0)
	assert m.time == pytest.approx(0.0)

def test_time_behaviour_clamp_default():
	m = LinearMotion(start_value=0.0, duration=1.0, change_value=1.0)

	m.update(5.0) # way past duration

	assert m.time == pytest.approx(1.0)
	assert m.get_value() == pytest.approx(1.0)

def test_time_behaviour_loop():
	m = LinearMotion(
		start_value=0.0,
		duration=1.0,
		change_value=1.0,
		time_behaviour=Motion.TimeBehaviour.LOOP
	)

	m.update(1.5) # wraps: 1.5 % 1.0 == 0.5

	assert m.time == pytest.approx(0.5)
	assert m.get_value() == pytest.approx(0.5)

def test_get_value_at_does_not_mutate_time():
	m = LinearMotion(start_value=0.0, duration=1.0, change_value=1.0)

	assert m.get_value_at(0.75) == pytest.approx(0.75)
	assert m.time == pytest.approx(0.0) # unaffected by get_value_at()

def test_composite_motion_sequences_children():
	# Two 1-second linear legs (0 -> 1, then 1 -> 2) chained into a single 2-second composite.
	# get_value_at() uses the composite's OWN time scale (0..2), not normalized 0..1.
	composite = CompositeMotion(start_value=0.0, duration=2.0, change_value=1.0)

	composite.add_motion(LinearMotion(start_value=0.0, duration=1.0, change_value=1.0))
	composite.add_motion(LinearMotion(start_value=1.0, duration=1.0, change_value=1.0))

	# Interior points only -- the exact leg boundary (t=1.0) depends on a strict "<" comparison
	# internal to CompositeMotion, not worth pinning down here.
	assert composite.get_value_at(0.5) == pytest.approx(0.5)
	assert composite.get_value_at(1.5) == pytest.approx(1.5)
