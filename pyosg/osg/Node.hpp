#pragma once

#include "callable.hpp"

PYOSG_DISABLE_WARNINGS

#include <osg/NodeVisitor>

PYOSG_ENABLE_WARNINGS

#include "pybind11x.hpp"

namespace pyx = pybind11x;

namespace pyosg {

namespace detail {
	using NodeSlots = pyx::PropertySlots<osg::Node, 1>;
	using NodeStorage = pyx::ProxyStorageOSG<osg::Node, NodeSlots>;

	constexpr size_t UpdateCallbackSlot = 0;

	using UpdateCallbackType = osg::NodeCallback;
	using UpdateCallbackWrapper = CallableCallback<
		osg::NodeCallback,
		void(osg::Node*, osg::NodeVisitor*),
		true
	>;

	// Pointers to class methods have always mystified me; the pieces are:
	//
	//    <$ReturnValue($Class::*)($MethodParams...)>(&$Method)
	//
	// TODO: There must be a way to make this less crazy?
	constexpr auto UpdateCallbackGetter =
		static_cast<osg::Callback*(osg::Node::*)()>(&osg::Node::getUpdateCallback)
	;

	constexpr auto UpdateCallbackSetter =
		static_cast<void(osg::Node::*)(osg::Callback*)>(&osg::Node::setUpdateCallback)
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
	inline auto node_update_callback_property_setter() {
		return node_callback_property_setter<
			UpdateCallbackSlot,
			UpdateCallbackSetter,
			UpdateCallbackGetter,
			UpdateCallbackType,
			UpdateCallbackWrapper
		>();
	}
}

void bind_Node(py::module_& m);

}
