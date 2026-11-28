from .conftest import refcmp

from OpenSceneGraph.osg import Object, Group, Vec2f, Vec3d, Vec4f, Quat, Matrixd

import gc

import pytest

def test_construction():
	o = Object(name="foo")

	assert o.name == "foo"
	assert refcmp(o, 1, 1)

	o0 = o
	o1 = o

	assert refcmp(o, 1, 3)

def test_destruction():
	deleted = []

	o = Object(name="bar", debug=lambda *a: deleted.append(True))

	del o

	gc.collect()

	assert deleted[0] == True

def test_inheritance():
	class MyObject(Object):
		pass

	o = MyObject(name="foo", dataVariance=Object.DYNAMIC)

	assert o.dataVariance == Object.DYNAMIC
	assert refcmp(o, 1, 1)

def test_userdata():
	o = Object()
	d = Object(name="DATA")

	o.userData = d

	assert o.userData.name == "DATA"
	assert refcmp(o, 1, 1)
	assert refcmp(d, 2, 1)

def test_uservalues_types():
	o = Object()

	values = {
		"b": True,
		"i": -7,
		"f": 0.25,
		"s": "hello",
		"v2": Vec2f(1, 2),
		"v3": Vec3d(1, 2, 3),
		"v4": Vec4f(1, 2, 3, 4),
		"q": Quat(0.5, Vec3d(0, 0, 1)),
		"m": Matrixd.translate(1, 2, 3),
	}

	for k, v in values.items():
		o.userValues[k] = v

	assert len(o.userValues) == len(values)
	assert sorted(o.userValues.keys()) == sorted(values.keys())

	for k, v in values.items():
		assert type(o.userValues[k]) is type(v)
		assert o.userValues[k] == v

def test_uservalues_mapping():
	o = Object()

	assert len(o.userValues) == 0
	assert "missing" not in o.userValues
	assert o.userValues.get("missing") is None

	with pytest.raises(KeyError):
		o.userValues["missing"]

	with pytest.raises(KeyError):
		del o.userValues["missing"]

	o.userValues["a"] = 1
	o.userValues["b"] = "two"

	assert dict(o.userValues.items()) == {"a": 1, "b": "two"}
	assert list(o.userValues) == ["a", "b"]
	assert o.userValues.pop("a") == 1
	assert "a" not in o.userValues
	assert o.userValues.setdefault("c", 3.5) == 3.5

	o.userValues.clear()

	assert len(o.userValues) == 0

# Assigning to an existing key keeps the stored C++ type (getUserValue<T>() needs an exact match).
def test_uservalues_existing_type_wins():
	o = Object()

	o.userValues["f"] = 1.5
	o.userValues["f"] = 2

	assert type(o.userValues["f"]) is float
	assert o.userValues["f"] == 2.0

	o.userValues["i"] = 1

	with pytest.raises(TypeError):
		o.userValues["i"] = "not an int"

	assert o.userValues["i"] == 1

	del o.userValues["i"]

	o.userValues["i"] = "now a string"

	assert o.userValues["i"] == "now a string"

def test_uservalues_rejects():
	o = Object()

	with pytest.raises(TypeError):
		o.userValues["t"] = (1, 2, 3)

	with pytest.raises(ValueError):
		o.userValues["big"] = 2 ** 40

	assert len(o.userValues) == 0

# Non-value user objects (here the debug= lifetime probe) share the container but are not values.
def test_uservalues_ignores_other_user_objects():
	o = Object(debug=lambda *a: None)

	assert o.userDataContainer.numUserObjects == 1
	assert len(o.userValues) == 0

	o.userValues["x"] = 1

	assert o.userValues.keys() == ["x"]
	assert o.userDataContainer.numUserObjects == 2

# A pure read must not create a UserDataContainer (ASCII .osgt omits a NULL one entirely).
def test_uservalues_read_creates_no_container():
	o = Object()

	assert "x" not in o.userValues
	assert len(o.userValues) == 0
	assert b"UserDataContainer" not in o.dumps("osgt")

	o.userValues["x"] = 1

	assert b"UserDataContainer" in o.dumps("osgt")

# Values as C++ setUserValue<T>() stores them, with types Python never creates itself (float,
# unsigned int, short, ...). A Group, because a serialized bare osg::Object loads as an
# osg::DummyObject, which writes back without its Name/UserDataContainer.
CPP_USER_VALUES = """#Ascii Object
#Version 162
#Generator OpenSceneGraph 3.6.5

osg::Group {
  UniqueID 1
  Name "cpp"
  UserDataContainer TRUE {
    osg::DefaultUserDataContainer {
      UniqueID 2
      UDC_UserObjects 4 {
        osg::FloatValueObject {
          UniqueID 3
          Name "f"
          Value 0.5
        }
        osg::UIntValueObject {
          UniqueID 4
          Name "u"
          Value 7
        }
        osg::ShortValueObject {
          UniqueID 5
          Name "s"
          Value -3
        }
        osg::StringValueObject {
          UniqueID 6
          Name "gltf.extras"
          Value "{\\"sc2_light\\": 1}"
        }
      }
    }
  }
}
"""

def test_uservalues_cpp_typed():
	o = Object.loads(CPP_USER_VALUES, "osgt")

	assert isinstance(o, Group)
	assert o.userValues["f"] == 0.5
	assert o.userValues["u"] == 7
	assert o.userValues["s"] == -3
	assert o.userValues["gltf.extras"] == '{"sc2_light": 1}'

	# Assignment keeps each stored C++ type, range-checked against it.
	o.userValues["f"] = 0.25
	o.userValues["u"] = 4000000000
	o.userValues["s"] = -32768

	with pytest.raises(ValueError):
		o.userValues["u"] = -1

	with pytest.raises(ValueError):
		o.userValues["s"] = 40000

	data = o.dumps("osgt")

	assert b"osg::FloatValueObject" in data
	assert b"osg::UIntValueObject" in data
	assert b"osg::ShortValueObject" in data
	assert b"osg::DoubleValueObject" not in data

	o2 = Object.loads(data, "osgt")

	assert dict(o2.userValues.items()) == dict(o.userValues.items())

@pytest.mark.parametrize("ext", ["osgt", "osgb", "osgx"])
def test_dumps_loads_roundtrip(ext):
	o = Object(name="round", dataVariance=Object.DYNAMIC)

	o.userValues["i"] = 3
	o.userValues["v"] = Vec3d(1, 2, 3)

	o2 = Object.loads(o.dumps(ext), ext)

	assert o2.name == "round"
	assert o2.dataVariance == Object.DYNAMIC
	assert dict(o2.userValues.items()) == dict(o.userValues.items())

def test_dumps_format():
	assert Object().dumps("osgt").startswith(b"#Ascii")
	assert not Object().dumps("osgb").startswith(b"#Ascii")

def test_loads_downcasts():
	g = Object.loads(Group(name="g").dumps("osgt"), "osgt")

	assert isinstance(g, Group)
	assert g.name == "g"
	assert refcmp(g, 1, 1)

def test_loads_errors():
	with pytest.raises(ValueError):
		Object.loads(b"not an osg file", "osgt")

	with pytest.raises(ValueError):
		Object.loads(b"", "no-such-extension")

# setUserValue() would silently replace a same-named non-value user object; userValues refuses.
def test_uservalues_name_collision():
	o = Object(debug=lambda *a: None)

	assert "pyosg.LifetimeProbe" not in o.userValues

	with pytest.raises(ValueError):
		o.userValues["pyosg.LifetimeProbe"] = 1

	with pytest.raises(KeyError):
		del o.userValues["pyosg.LifetimeProbe"]

	assert o.userDataContainer.numUserObjects == 1
	assert o.userDataContainer.getUserObject(0).name == "pyosg.LifetimeProbe"
	assert len(o.userValues) == 0

DUPLICATE_USER_VALUES = """#Ascii Object
#Version 162
#Generator OpenSceneGraph 3.6.5

osg::Group {
  UniqueID 1
  UserDataContainer TRUE {
    osg::DefaultUserDataContainer {
      UniqueID 2
      UDC_UserObjects 3 {
        osg::IntValueObject {
          UniqueID 3
          Name "d"
          Value 1
        }
        osg::IntValueObject {
          UniqueID 4
          Name "e"
          Value 3
        }
        osg::IntValueObject {
          UniqueID 5
          Name "d"
          Value 2
        }
      }
    }
  }
}
"""

# Duplicate names resolve to the first match (as getUserValue()/getUserObjectIndex() do) and are
# listed once; deleting the first exposes the next.
def test_uservalues_duplicate_names():
	o = Object.loads(DUPLICATE_USER_VALUES, "osgt")

	assert o.userDataContainer.numUserObjects == 3
	assert o.userValues.keys() == ["d", "e"]
	assert len(o.userValues) == 2
	assert o.userValues["d"] == 1

	o.userValues["d"] = 5

	assert o.userValues["d"] == 5

	del o.userValues["d"]

	assert o.userValues["d"] == 2
	assert o.userDataContainer.numUserObjects == 2
