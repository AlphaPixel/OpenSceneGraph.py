#include "Bound.hpp"

namespace pyosg {

void bind_Bound(py::module_& m) {
	auto bbf = detail::bind_BoundingBox<osg::BoundingBoxf>(m, "BoundingBoxf");
	auto bbd = detail::bind_BoundingBox<osg::BoundingBoxd>(m, "BoundingBoxd");

#ifdef OSG_USE_FLOAT_BOUNDINGBOX
	m.add_object("BoundingBox", bbf);
#else
	m.add_object("BoundingBox", bbd);
#endif

	auto bsf = detail::bind_BoundingSphere<osg::BoundingSpheref>(m, "BoundingSpheref");
	auto bsd = detail::bind_BoundingSphere<osg::BoundingSphered>(m, "BoundingSphered");

#ifdef OSG_USE_FLOAT_BOUNDINGSPHERE
	m.add_object("BoundingSphere", bsf);
#else
	m.add_object("BoundingSphere", bsf);
#endif
}

}
