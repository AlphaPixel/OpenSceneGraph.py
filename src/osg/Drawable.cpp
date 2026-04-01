#include "callable.hpp"

PYOSG_DISABLE_WARNINGS

#include <osg/Drawable>

PYOSG_ENABLE_WARNINGS

#include "pybind11x.hpp"

namespace pyx = pybind11x;

namespace pyosg {

namespace detail {
	using DrawableSlots = pyx::PropertySlots<osg::Drawable, 1>;
	using DrawableStorage = pyx::ProxyStorageOSG<osg::Drawable, DrawableSlots>;

	constexpr size_t DrawableCallbackSlot = 0;

	using DrawableCallbackType = osg::Drawable::DrawCallback;
	using DrawableCallbackWrapper = CallableCallback<
		osg::Drawable::DrawCallback,
		void(osg::RenderInfo&, const osg::Drawable*) const,
		false
	>;

	constexpr auto DrawableCallbackGetter =
		static_cast<osg::Drawable::DrawCallback*(osg::Drawable::*)()>(
			&osg::Drawable::getDrawCallback
		)
	;

	constexpr auto DrawableCallbackSetter =
		static_cast<void(osg::Drawable::*)(osg::Drawable::DrawCallback*)>(
			&osg::Drawable::setDrawCallback
		)
	;

	template<size_t I, auto Setter, auto Getter, typename Callback, typename Wrapper>
	auto callback_property_setter() {
		return [](osg::Drawable& self, py::object obj) {
			applyCallback<Setter, Callback, Wrapper>(self, obj);

			auto* ptr = (self.*Getter)();
			auto& slots = DrawableStorage::get(self)->template proxy<DrawableSlots>();

			slots.set(I, obj, ptr);
		};
	}

	template<>
	struct CallbackMethod<osg::Drawable::DrawCallback> {
		template<typename Self, typename Fn>
		static void invoke(Self* self, Fn& fn, osg::RenderInfo& ri) {
			py::gil_scoped_acquire gil;

			fn(ri);
		}
	};

	template<>
	class CallableCallback<
		osg::Drawable::DrawCallback,
		void(osg::RenderInfo&, const osg::Drawable*) const,
		false
	>: public osg::Drawable::DrawCallback {
	public:
		explicit CallableCallback(py::object fn): _fn(std::move(fn)) {}

		void drawImplementation(osg::RenderInfo& ri, const osg::Drawable* d) const override {
			py::gil_scoped_acquire gil;

			_fn(ri, d);
		}

	private:
		py::object _fn;
	};

	inline auto draw_callback_property_setter() {
		return callback_property_setter<
			DrawableCallbackSlot,
			DrawableCallbackSetter,
			DrawableCallbackGetter,
			DrawableCallbackType,
			DrawableCallbackWrapper
		>();
	}

	template<>
	void kwargs_init(osg::Drawable& self, const py::kwargs& kwargs) {
	}

	class Drawable: public osg::Drawable {
	public:
		struct DrawCallback: public osg::Drawable::DrawCallback {
			void drawImplementation(osg::RenderInfo& ri, const osg::Drawable* d) const override {
				py::gil_scoped_acquire gil;

				PYBIND11_OVERRIDE(
					void,
					osg::Drawable::DrawCallback,
					drawImplementation,
					ri,
					d
				);
			}
		};

		void drawImplementation(osg::RenderInfo& ri) const override {
			py::gil_scoped_acquire gil;

			PYBIND11_OVERRIDE(
				void,
				osg::Drawable,
				drawImplementation,
				ri
			);
		}

		osg::BoundingSphere computeBound() const override {
			PYBIND11_OVERRIDE(
				osg::BoundingSphere,
				osg::Drawable,
				computeBound
			);
		}

		osg::BoundingBox computeBoundingBox() const override {
			PYBIND11_OVERRIDE(
				osg::BoundingBox,
				osg::Drawable,
				computeBoundingBox
			);
		}
	};
}

void bind_Drawable(py::module_& m) {
	py::class_<osg::RenderInfo>(m, "RenderInfo")
		.def_property_readonly("contextID", &osg::RenderInfo::getContextID)
		// TODO: Add setter support!?
		.def_property_readonly("state",
			py::overload_cast<>(&osg::RenderInfo::getState),
			py::return_value_policy::reference
		)
		// TODO: Add setter support!?
		.def_property_readonly("view",
			py::overload_cast<>(&osg::RenderInfo::getView),
			py::return_value_policy::reference
		)
	;

	auto drawable = py::class_<
		osg::Drawable,
		detail::Drawable,
		osg::Node,
		osg::ref_ptr<osg::Drawable>
	>(m, "Drawable");

	py::class_<
		osg::Drawable::DrawCallback,
		detail::Drawable::DrawCallback,
		osg::Object,
		osg::ref_ptr<osg::Drawable::DrawCallback>
	>(drawable, "DrawCallback")
		.def(py::init<>())
	;

	drawable
		// .def(py::init_alias<>())
		.def(py::init<>())
		/* .def(py::init([](py::kwargs kwargs) {
			osg::ref_ptr<osg::Drawable> d = new osg::Drawable();

			detail::kwargs_init(*d, kwargs);

			return d;
		})) */
		// TODO: Do I use detail::Drawable here?
		//.def("drawImplementation", [](osg::Drawable& self, osg::RenderInfo& ri) {
		//	self.drawImplementation(ri);
		//})
		.def("computeBound", &osg::Drawable::computeBound)
		.def("computeBoundingBox", &osg::Drawable::computeBoundingBox)
		.def_property(
			"drawCallback",
			detail::DrawableSlots::getter<detail::DrawableCallbackSlot>(
				detail::DrawableCallbackGetter
			),
			detail::draw_callback_property_setter()
		)
		.def_property("initialBound",
			py::cpp_function(
				&osg::Drawable::getInitialBound,
				py::return_value_policy::reference
			),
			py::cpp_function(
				&osg::Drawable::setInitialBound,
				py::keep_alive<1, 2>()
			)
		)
		.def_property("useVertexBufferObjects",
			&osg::Drawable::getUseVertexBufferObjects,
			&osg::Drawable::setUseVertexBufferObjects
		)
		.def_property("useVertexArrayObject",
			&osg::Drawable::getUseVertexArrayObject,
			&osg::Drawable::setUseVertexArrayObject
		)
	;
}

}
