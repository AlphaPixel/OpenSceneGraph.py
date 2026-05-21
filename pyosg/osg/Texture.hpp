#pragma once

#include "../pyosg.hpp"

PYOSG_DISABLE_WARNINGS

#include <osg/Texture2D>

PYOSG_ENABLE_WARNINGS

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
		// apply (pure virtual)
        //
		// compileGLObjects
		// resizeGLObjectBuffers
		// releaseGLObjects
        //
		// isDirty
	};
}

void bind_Texture(py::module_& m);

}
