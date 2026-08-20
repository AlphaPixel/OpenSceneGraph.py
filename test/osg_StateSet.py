#vimrun! pytest -sv ../test/osg_StateSet.py

# from .conftest import f32, floatif, refcmp

import pytest

from OpenSceneGraph.osg import StateSet, StateAttribute, Program, Texture2D, Uniform, Vec3f, Matrixf
from OpenSceneGraph.GL import GL_DEPTH_TEST, GL_BLEND, GL_CULL_FACE

def test_uniforms_append(uniform_init):
	ss = StateSet()

	for ty, val in uniform_init:
		u = Uniform(ty, str(ty).split(".")[-1])

		u.value = val

		ss.uniforms.append(u)

	assert len(ss.uniforms) == len(uniform_init)

def test_uniforms_extend(uniform_init):
	ss = StateSet()

	# Let the values stay at whatever the DEFAULTS are.
	ss.uniforms.extend(Uniform(ty, str(ty).split(".")[-1]) for ty, val in uniform_init)

	assert ss.uniforms["BOOL"].value == False
	assert ss.uniforms["INT"].value == 0
	assert ss.uniforms["FLOAT_VEC3"].value == Vec3f()

def test_uniform_mutation():
	ss = StateSet()

	ss.uniforms["float"] = 1.2

	addr = ss.uniforms["float"].addr

	assert ss.uniforms["float"].value == pytest.approx(1.2)

	ss.uniforms["float"] = 3.4

	assert ss.uniforms["float"].value == pytest.approx(3.4)
	assert ss.uniforms["float"].addr == addr

	ss.uniforms["double"] = (Uniform.DOUBLE, 56.78)

	assert ss.uniforms["double"].value == 56.78
	assert len(ss.uniforms) == 2

def test_uniforms_array_tuple_assignment():
	ss = StateSet()

	ss.uniforms["lights"] = (Vec3f(1, 0, 0), Vec3f(0, 1, 0))

	u = ss.uniforms["lights"]

	assert len(u) == 2
	assert u[0] == Vec3f(1, 0, 0)
	assert u[1] == Vec3f(0, 1, 0)

def test_uniforms_array_tuple_three():
	ss = StateSet()

	ss.uniforms["pts"] = (Vec3f(1, 0, 0), Vec3f(0, 1, 0), Vec3f(0, 0, 1))

	u = ss.uniforms["pts"]

	assert len(u) == 3
	assert u[2] == Vec3f(0, 0, 1)

def test_texture_attributes_mapping():
	ss = StateSet()
	t0 = Texture2D()
	t1 = Texture2D()

	ss.textureAttributes[0] = t0
	ss.textureAttributes[1] = (t1, StateAttribute.ON)

	assert ss.textureAttributes[0] is t0
	assert ss.textureAttributes[1] is t1
	assert len(ss.textureAttributes) == 2
	assert ss.textureAttributes.keys() == [0, 1]
	assert 0 in ss.textureAttributes
	assert 2 not in ss.textureAttributes

	ss.uniforms["u"] = 1.0

	assert ss.uniforms["u"].value == pytest.approx(1.0)

	del ss.textureAttributes[0]

	assert len(ss.textureAttributes) == 1
	assert ss.textureAttributes.keys() == [1]
	assert 0 not in ss.textureAttributes

def test_uniforms_get_pop_clear():
	ss = StateSet()

	ss.uniforms["a"] = 1.0
	ss.uniforms["b"] = 2.0

	assert ss.uniforms.get("a").value == pytest.approx(1.0)
	assert ss.uniforms.get("missing") is None
	assert ss.uniforms.get("missing", "fallback") == "fallback"

	popped = ss.uniforms.pop("a")

	assert popped.value == pytest.approx(1.0)
	assert "a" not in ss.uniforms
	assert len(ss.uniforms) == 1

	assert ss.uniforms.pop("missing", "fallback") == "fallback"

	with pytest.raises(KeyError):
		ss.uniforms.pop("missing")

	ss.uniforms.clear()

	assert len(ss.uniforms) == 0

def test_uniforms_setdefault():
	ss = StateSet()

	ss.uniforms["a"] = 1.0

	# already present -- returns the existing value, unchanged
	assert ss.uniforms.setdefault("a", 99.0).value == pytest.approx(1.0)

	# absent -- sets it, then returns the (now-existing) value
	created = ss.uniforms.setdefault("b", 2.0)

	assert created.value == pytest.approx(2.0)
	assert ss.uniforms["b"] is created
	assert len(ss.uniforms) == 2

def test_uniforms_pop_and_clear_release_when_no_other_ref():
	# Same reasoning as Group's version of this test: len() dropping to 0 doesn't prove the
	# Uniform objects were actually destroyed rather than kept alive by a leaked MapSlotCache
	# entry. No local variables are kept beyond `popped` on purpose. (Uniform's constructor
	# used to bypass kwargs_init entirely -- debug= failed here until that was fixed, see
	# test_kwargs_init_debug_and_name in test/osg_Uniform.py.)
	deleted = []
	dbg = lambda addr, cls, name: deleted.append(name)

	ss = StateSet()

	ss.uniforms["a"] = Uniform(Uniform.FLOAT, "a", debug=dbg)
	ss.uniforms["b"] = Uniform(Uniform.FLOAT, "b", debug=dbg)

	popped = ss.uniforms.pop("a")

	assert popped.name == "a"
	assert deleted == []  # `popped` is still holding a reference to it

	del popped

	assert deleted == ["a"]

	ss.uniforms.clear()

	assert deleted == ["a", "b"]

def test_texture_attributes_pop_and_clear_release_when_no_other_ref():
	# Same reasoning, but through the textureAttributes MappingProxy specialization instead of
	# uniforms -- proxy pop()/clear() are the same shared code across every MappingProxy, so
	# this is complementary coverage via a second owner, not redundant.
	deleted = []
	dbg = lambda addr, cls, name: deleted.append(name)

	ss = StateSet()

	ss.textureAttributes[0] = Texture2D(name="t0", debug=dbg)
	ss.textureAttributes[1] = Texture2D(name="t1", debug=dbg)

	popped = ss.textureAttributes.pop(0)

	assert deleted == []  # `popped` is still holding a reference to it

	del popped

	assert deleted == ["t0"]

	ss.textureAttributes.clear()

	assert deleted == ["t0", "t1"]

def test_texture_attributes_get_pop_clear():
	ss = StateSet()
	t0 = Texture2D()
	t1 = Texture2D()

	ss.textureAttributes[0] = t0
	ss.textureAttributes[1] = t1

	assert ss.textureAttributes.get(0) is t0
	assert ss.textureAttributes.get(99) is None
	assert ss.textureAttributes.get(99, "fallback") == "fallback"

	popped = ss.textureAttributes.pop(0)

	assert popped is t0
	assert 0 not in ss.textureAttributes
	assert len(ss.textureAttributes) == 1

	assert ss.textureAttributes.pop(99, "fallback") == "fallback"

	with pytest.raises(KeyError):
		ss.textureAttributes.pop(99)

	ss.textureAttributes.clear()

	assert len(ss.textureAttributes) == 0

def test_attributes_get_pop_clear():
	ss = StateSet()
	p = Program(name="p")

	ss.attributes[StateAttribute.PROGRAM] = p

	assert ss.attributes.get(StateAttribute.PROGRAM) is p
	assert ss.attributes.get(StateAttribute.TEXTURE) is None

	popped = ss.attributes.pop(StateAttribute.PROGRAM)

	assert popped is p
	assert len(ss.attributes) == 0

	with pytest.raises(KeyError):
		ss.attributes.pop(StateAttribute.PROGRAM)

def test_attributes_mapping():
	ss = StateSet()
	p = Program(name="p")

	# The subscript key is the attribute's OWN `StateAttribute::Type` -- it's not inferred, so
	# it must be repeated even though `p` already knows its own type.
	ss.attributes[StateAttribute.PROGRAM] = p

	assert ss.attributes[StateAttribute.PROGRAM] is p
	assert len(ss.attributes) == 1
	assert ss.attributes.keys() == [StateAttribute.PROGRAM]
	assert StateAttribute.PROGRAM in ss.attributes
	assert StateAttribute.TEXTURE not in ss.attributes

	del ss.attributes[StateAttribute.PROGRAM]

	assert len(ss.attributes) == 0
	assert StateAttribute.PROGRAM not in ss.attributes

def test_attributes_tuple_mode():
	ss = StateSet()
	p = Program(name="p")

	ss.attributes[StateAttribute.PROGRAM] = (p, StateAttribute.OVERRIDE)

	assert ss.attributes[StateAttribute.PROGRAM] is p

def test_attributes_append_infers_key():
	ss = StateSet()
	p = Program(name="p")

	# append()/extend() read the key from `p.type` -- this is the syntax that sidesteps having
	# to name `StateAttribute.PROGRAM` a second time.
	ss.attributes.append(p)

	assert ss.attributes[StateAttribute.PROGRAM] is p
	assert len(ss.attributes) == 1

def test_attributes_key_type_mismatch():
	ss = StateSet()
	p = Program(name="p")

	with pytest.raises(ValueError):
		ss.attributes[StateAttribute.TEXTURE] = p

def test_modes_mapping():
	ss = StateSet()

	ss.modes[GL_DEPTH_TEST] = StateAttribute.OFF
	ss.modes[GL_BLEND] = StateAttribute.ON | StateAttribute.OVERRIDE

	assert ss.modes[GL_DEPTH_TEST] == StateAttribute.OFF
	assert ss.modes[GL_BLEND] == StateAttribute.ON | StateAttribute.OVERRIDE
	assert len(ss.modes) == 2
	assert sorted(ss.modes.keys()) == sorted((GL_DEPTH_TEST, GL_BLEND))
	assert GL_DEPTH_TEST in ss.modes
	assert GL_CULL_FACE not in ss.modes

	del ss.modes[GL_DEPTH_TEST]

	assert len(ss.modes) == 1
	assert GL_DEPTH_TEST not in ss.modes

def test_modes_get_pop_clear():
	ss = StateSet()

	ss.modes[GL_DEPTH_TEST] = StateAttribute.OFF
	ss.modes[GL_BLEND] = StateAttribute.ON

	assert ss.modes.get(GL_DEPTH_TEST) == StateAttribute.OFF
	assert ss.modes.get(GL_CULL_FACE) is None
	assert ss.modes.get(GL_CULL_FACE, "fallback") == "fallback"

	popped = ss.modes.pop(GL_DEPTH_TEST)

	assert popped == StateAttribute.OFF
	assert GL_DEPTH_TEST not in ss.modes
	assert len(ss.modes) == 1

	assert ss.modes.pop(GL_CULL_FACE, "fallback") == "fallback"

	with pytest.raises(KeyError):
		ss.modes.pop(GL_CULL_FACE)

	ss.modes.clear()

	assert len(ss.modes) == 0

def test_modes_setdefault():
	ss = StateSet()

	ss.modes[GL_DEPTH_TEST] = StateAttribute.OFF

	# already present -- returns the existing value, unchanged
	assert ss.modes.setdefault(GL_DEPTH_TEST, StateAttribute.ON) == StateAttribute.OFF

	# absent -- sets it, then returns the (now-existing) value
	assert ss.modes.setdefault(GL_BLEND, StateAttribute.ON) == StateAttribute.ON
	assert ss.modes[GL_BLEND] == StateAttribute.ON
	assert len(ss.modes) == 2

# Same ValueMappingProxy shape as .modes[] above (see State.hpp's DefinesTag) -- string keys
# instead of GL enum keys, but otherwise identical get/set/del/keys/contains/pop/setdefault
# behavior, so these mirror the .modes[] tests directly rather than inventing new coverage shapes.
def test_defines_mapping():
	ss = StateSet()

	ss.defines["FOO"] = StateAttribute.ON
	ss.defines["BAR"] = StateAttribute.ON | StateAttribute.OVERRIDE

	assert ss.defines["FOO"] == StateAttribute.ON
	assert ss.defines["BAR"] == StateAttribute.ON | StateAttribute.OVERRIDE
	assert len(ss.defines) == 2
	assert sorted(ss.defines.keys()) == sorted(("FOO", "BAR"))
	assert "FOO" in ss.defines
	assert "BAZ" not in ss.defines

	del ss.defines["FOO"]

	assert len(ss.defines) == 1
	assert "FOO" not in ss.defines

def test_defines_get_pop_clear():
	ss = StateSet()

	ss.defines["FOO"] = StateAttribute.ON
	ss.defines["BAR"] = StateAttribute.ON

	assert ss.defines.get("FOO") == StateAttribute.ON
	assert ss.defines.get("MISSING") is None
	assert ss.defines.get("MISSING", "fallback") == "fallback"

	popped = ss.defines.pop("FOO")

	assert popped == StateAttribute.ON
	assert "FOO" not in ss.defines
	assert len(ss.defines) == 1

	assert ss.defines.pop("MISSING", "fallback") == "fallback"

	with pytest.raises(KeyError):
		ss.defines.pop("MISSING")

	ss.defines.clear()

	assert len(ss.defines) == 0

def test_defines_setdefault():
	ss = StateSet()

	ss.defines["FOO"] = StateAttribute.OFF

	# already present -- returns the existing value, unchanged
	assert ss.defines.setdefault("FOO", StateAttribute.ON) == StateAttribute.OFF

	# absent -- sets it, then returns the (now-existing) value
	assert ss.defines.setdefault("BAR", StateAttribute.ON) == StateAttribute.ON
	assert ss.defines["BAR"] == StateAttribute.ON
	assert len(ss.defines) == 2

# The actual real-world call shape this binding was added FOR (see 11-sketchfab.py's
# OSGX_PBRIBL_AO wiring) -- setDefine()'s single-arg overload sets the define's own value string
# to "" (a flag-style, #ifdef-tested define, not a `#define NAME value` substitution). There's no
# Python-facing way to read that value string back yet (only the OverrideValue half of the
# DefinePair is exposed -- see DefinesTag's own comment in State.hpp), so this only asserts the
# round-trip on the half that IS exposed; it does not prove the value string landed correctly.
def test_defines_set_matches_setDefine_single_arg_overload():
	ss = StateSet()

	ss.defines["OSGX_PBRIBL_AO"] = StateAttribute.ON

	assert ss.defines["OSGX_PBRIBL_AO"] == StateAttribute.ON
