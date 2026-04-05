#pragma once

#include "lifetime-probe.hpp"

PYOSG_DISABLE_WARNINGS

#include <osgDB/Registry>

PYOSG_ENABLE_WARNINGS

namespace pyosg {

namespace detail {
	// This class exists to permit Python code like: `o = osg.Object`.
	class Object: public osg::Object {
	public:
		PYOSG_DISABLE_WARNINGS

		// It's weird not using `pyosg` here, but doing so would break serialization.
		META_Object(osg, Object)

		PYOSG_ENABLE_WARNINGS

		using osg::Object::Object;

		explicit Object(): osg::Object() {}
		// ~Object() override {}

		// TODO: These are used often, and Python subclasses MIGHT need to override them!
		// void resizeGLObjectBuffers(unsigned int) override
		// void releaseGLObjects(osg::State* = 0) const override
	};

	class UserDataContainer: public osg::UserDataContainer {
	public:
		using osg::UserDataContainer::UserDataContainer;

		// void setUserData(Referenced* obj) = 0;
		// Referenced* getUserData() = 0;
		// const Referenced* getUserData() const  = 0;
		// unsigned int addUserObject(Object* obj)  = 0;
		// void setUserObject(unsigned int i, Object* obj)  = 0;
		// void removeUserObject(unsigned int i)  = 0;
		// unsigned int getUserObjectIndex(const osg::Object* obj, unsigned int startPos=0) const = 0;
		// unsigned int getUserObjectIndex(const std::string& name, unsigned int startPos=0) const = 0;
		// void setDescriptions(const DescriptionList& descriptions) = 0;
		// DescriptionList& getDescriptions() = 0;
		// const DescriptionList& getDescriptions() const = 0;
		// unsigned int getNumDescriptions() const = 0;
		// void addDescription(const std::string& desc) = 0;

		unsigned int getNumUserObjects() const override {
			PYBIND11_OVERRIDE_PURE(
				unsigned int,
				osg::UserDataContainer,
				getNumUserObjects
			);
		}

		// const Object* getUserObject(unsigned int i) const  = 0;
		osg::Object* getUserObject(unsigned int i) override {
			PYBIND11_OVERRIDE_PURE(
				osg::Object*,
				osg::UserDataContainer,
				getUserObject
				i
			);
		}
	};
}

void bind_Object(py::module_& m);

}
