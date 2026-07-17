#pragma once

#include "../pyosg.hpp"

PYOSG_DISABLE_WARNINGS

#include <osg/Texture2D>
#include <osg/TextureCubeMap>

PYOSG_ENABLE_WARNINGS

#include "pybind11x.hpp"

namespace pyx = pybind11x;

namespace pyosg {

namespace detail {
	class Texture: public osg::Texture {
	public:
		// Texture(): osg::Texture() {}

		// getType
		// isTextureAttribute
		//
		// getTextureTarget (pure virtual)
		//
		// getTextureWidth
		// getTextureHeight
		// getTextureDepth
		//
		// setImage (pure virtual)
		// getImage (pure virtual)
		// getImage const (pure virtual)
		// getNumImages (pure virtual)
		//
		// virtual void apply(State& state) const = 0;

		void apply(osg::State& state) const override {
			PYBIND11_OVERRIDE_PURE(
				void,
				osg::Texture,
				apply,
				state
			);
		}

		// compileGLObjects
		// resizeGLObjectBuffers
		// releaseGLObjects
		//
		// isDirty
	};
}

void bind_Texture(py::module_& m);

}
