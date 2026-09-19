#pragma once

#include "callable.hpp"

OSGX_DISABLE_WARNINGS

#include <osg/NodeVisitor>

OSGX_ENABLE_WARNINGS

#include "pybind11x-osg.hpp"

namespace pyx = pybind11x;

namespace pyosg {

namespace detail {
	using NodeSlots = pyx::PropertySlots<osg::Node, 2>;
	using NodeStorage = pyx::ProxyStorageOSG<osg::Node, NodeSlots>;

	constexpr size_t UpdateCallbackSlot = 0;
	constexpr size_t EventCallbackSlot = 1;

	using UpdateCallbackType = osg::NodeCallback;
	using UpdateCallbackWrapper = CallableCallback<
		osg::NodeCallback,
		void(osg::Node*, osg::NodeVisitor*),
		true
	>;

	// NOTE: setUpdateCallback/setEventCallback are each overloaded with a member TEMPLATE
	// (setX(const ref_ptr<T>&), for convenience) alongside the plain setX(Callback*) - that
	// template poisons plain `auto` deduction (and overload_cast) for the whole set, same as
	// Bound.hpp's expandBy/expandRadiusBy; static_cast's explicit target type is what lets the
	// compiler pick the non-template overload here.
	constexpr auto UpdateCallbackGetter = py::overload_cast<>(&osg::Node::getUpdateCallback);
	constexpr auto UpdateCallbackSetter =
		static_cast<void(osg::Node::*)(osg::Callback*)>(&osg::Node::setUpdateCallback)
	;
	constexpr auto EventCallbackGetter = py::overload_cast<>(&osg::Node::getEventCallback);
	constexpr auto EventCallbackSetter =
		static_cast<void(osg::Node::*)(osg::Callback*)>(&osg::Node::setEventCallback)
	;

	// Slot-backed callback setter. We canonicalize the stored pointer via the getter so SlotCache
	// compares the same pointer representation the getter will later return.
	template<size_t I, auto Setter, auto Getter, typename Callback, typename Wrapper>
	auto node_callback_property_setter() {
		return [](osg::Node& self, py::object obj) {
			applyCallback<Setter, Callback, Wrapper>(self, obj);

			auto* ptr = (self.*Getter)();
			auto& slots = NodeStorage::get(self)->template proxy<NodeSlots>();

			slots.set(I, obj, ptr);
		};
	}

	// Combines all of the "glue" above into a single, reusable entry point.
	//
	// The isinstance-check/cast type here is osg::Callback, NOT UpdateCallbackType (NodeCallback) --
	// real OSG's Node::setUpdateCallback()/setEventCallback() already take a plain osg::Callback*
	// (the modern, unified callback entry point; NodeCallback::run() only exists to adapt IT to the
	// "old style" operator()(Node*, NodeVisitor*) method, per NodeCallback's own doc comment in
	// osg/Callback). Using osg::Callback here is a strict superset of the old NodeCallback-only
	// check - any NodeCallback instance still passes it (NodeCallback IS-A Callback) - so this
	// doesn't change behavior for existing NodeCallback-based code, it just also accepts a plain
	// Callback subclass overriding run() directly. UpdateCallbackWrapper is UNCHANGED (still
	// NodeCallback-shaped): it's a separate concern, wrapping a bare Python callable for the
	// Node-visitor-specific (node, nv) convenience signature, not affected by this.
	inline auto node_update_callback_property_setter() {
		return node_callback_property_setter<
			UpdateCallbackSlot,
			UpdateCallbackSetter,
			UpdateCallbackGetter,
			osg::Callback,
			UpdateCallbackWrapper
		>();
	}

	inline auto node_event_callback_property_setter() {
		return node_callback_property_setter<
			EventCallbackSlot,
			EventCallbackSetter,
			EventCallbackGetter,
			osg::Callback,
			UpdateCallbackWrapper
		>();
	}
}

void bind_Node(py::module_& m);

}
