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
	// Shared setters used by both `bind_Texture()`'s `.def_property()` calls and
	// `kwargs_init_own()` -- keeps the parsing/validation logic for each property in one place.
	inline auto texture_wrap_property_setter() {
		return [](osg::Texture& self, py::object obj) {
			if(py::isinstance<osg::Texture::WrapMode>(obj)) {
				auto v = obj.cast<osg::Texture::WrapMode>();

				self.setWrap(osg::Texture::WrapParameter::WRAP_S, v);
				self.setWrap(osg::Texture::WrapParameter::WRAP_T, v);
				self.setWrap(osg::Texture::WrapParameter::WRAP_R, v);
			}

			// Variable arity (1-3 elements, S/T/R in order): tried largest-first via exact-arity
			// unpacks rather than a single cascading `if(n >= k)` -- each branch below is now
			// also immune to the "string happens to satisfy isinstance<sequence>" trap (see
			// `pyx::try_unpack_sequence`), which an unconditional `obj.cast<py::sequence>()` with
			// no isinstance guard at all would not be.
			else if(auto vals3 = pyx::try_unpack_sequence<
				osg::Texture::WrapMode, osg::Texture::WrapMode, osg::Texture::WrapMode
			>(obj)) {
				auto& [s, t, r] = *vals3;

				self.setWrap(osg::Texture::WrapParameter::WRAP_S, s);
				self.setWrap(osg::Texture::WrapParameter::WRAP_T, t);
				self.setWrap(osg::Texture::WrapParameter::WRAP_R, r);
			}

			else if(auto vals2 = pyx::try_unpack_sequence<
				osg::Texture::WrapMode, osg::Texture::WrapMode
			>(obj)) {
				auto& [s, t] = *vals2;

				self.setWrap(osg::Texture::WrapParameter::WRAP_S, s);
				self.setWrap(osg::Texture::WrapParameter::WRAP_T, t);
			}

			else if(auto vals1 = pyx::try_unpack_sequence<osg::Texture::WrapMode>(obj)) {
				self.setWrap(osg::Texture::WrapParameter::WRAP_S, std::get<0>(*vals1));
			}

			else throw py::type_error(
				"wrap must be WrapMode or sequence of 1-3 WrapMode values (S, T, R)"
			);
		};
	}

	inline auto texture_filter_property_setter() {
		return [](osg::Texture& self, py::object obj) {
			if(py::isinstance<osg::Texture::FilterMode>(obj)) {
				auto v = obj.cast<osg::Texture::FilterMode>();

				// MAG filter only accepts LINEAR or NEAREST - strip mipmap component
				osg::Texture::FilterMode mag =
					(v == osg::Texture::NEAREST ||
					 v == osg::Texture::NEAREST_MIPMAP_LINEAR ||
					 v == osg::Texture::NEAREST_MIPMAP_NEAREST)
					? osg::Texture::NEAREST
					: osg::Texture::LINEAR
				;

				self.setFilter(osg::Texture::FilterParameter::MIN_FILTER, v);
				self.setFilter(osg::Texture::FilterParameter::MAG_FILTER, mag);
			}

			// Variable arity (1-2 elements, MIN/MAG in order) -- same chained exact-arity
			// approach as `wrap` above.
			else if(auto vals2 = pyx::try_unpack_sequence<
				osg::Texture::FilterMode, osg::Texture::FilterMode
			>(obj)) {
				auto& [min, mag] = *vals2;

				self.setFilter(osg::Texture::FilterParameter::MIN_FILTER, min);
				self.setFilter(osg::Texture::FilterParameter::MAG_FILTER, mag);
			}

			else if(auto vals1 = pyx::try_unpack_sequence<osg::Texture::FilterMode>(obj)) {
				self.setFilter(osg::Texture::FilterParameter::MIN_FILTER, std::get<0>(*vals1));
			}

			else throw py::type_error(
				"filter must be FilterMode or sequence of 1-2 FilterMode values (MIN, MAG)"
			);
		};
	}

	// TODO: Convert `image` to `pyx::*Proxy` -- no identity/keep_alive tracking yet, matching the
	// pre-existing `.def_property("image", ...)` this replaces.
	inline auto texture_image_property_setter() {
		return [](osg::Texture& self, py::object obj) {
			// A bare `osg.Image` isn't `py::sequence`-like, so `try_unpack_sequence<Image*>`
			// (arity 1) can never match one -- that branch used to be unreachable dead code and
			// `t.image = img` always fell through to the "(face, Image) required" error. Check
			// the direct-instance case first instead of trying to fake it through the sequence
			// unpacker.
			if(py::isinstance<osg::Image>(obj)) {
				self.setImage(0, obj.cast<osg::Image*>());
			}

			else if(auto vals = pyx::try_unpack_sequence<unsigned int, osg::Image*>(obj)) {
				auto& [face, img] = *vals;

				self.setImage(face, img);
			}

			else throw py::type_error("image must be osg.Image or (face, osg.Image)");
		};
	}

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
