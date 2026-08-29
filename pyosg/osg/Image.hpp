#pragma once

#include "../pyosg.hpp"

OSGX_DISABLE_WARNINGS

#include <osg/Image>

OSGX_ENABLE_WARNINGS

namespace pyosg {

namespace detail {
	/* class Image: public osg::Image {
	public:
		virtual void readImageFromCurrentTexture(unsigned int contextID, bool copyMipMapsIfAvailable, GLenum type = GL_UNSIGNED_BYTE, unsigned int face = 0);
	}; */
}

void bind_Image(py::module_& m);

}
