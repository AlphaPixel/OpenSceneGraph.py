#!/usr/bin/env python3

"""03 - A scrolling history of the model's relative per-layer hidden-state change."""

import ctypes
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("OSG_WINDOW", "50 50 1200 800")
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pyosg_example import window_size

from OpenSceneGraph import *
from OpenSceneGraph.GL import *

from llm_common import (
	CUDAInteropVBO, CausalLMStepper, ResponseText, TokenStepController,
	configure_glowing_points, causal_lm_arguments
)


HISTORY = 96

KERNEL_SOURCE = b"""
extern "C" __global__ void writeLayerHistory(float* positions, const float* changes,
	int layers, int slot, int history, int clear) {
	int i = blockIdx.x * blockDim.x + threadIdx.x;

	if(clear) {
		if(i >= layers * history) return;

		int layer = i % layers;
		int sample = i / layers;
		float y = layers > 1 ? 6.0f * layer / (layers - 1) - 3.0f : 0.0f;
		positions[i * 3 + 0] = (float)sample;
		positions[i * 3 + 1] = y;
		positions[i * 3 + 2] = 0.0f;
		return;
	}

	if(i >= layers) return;

	int layer = i;
	i = slot * layers + layer;
	float y = layers > 1 ? 6.0f * layer / (layers - 1) - 3.0f : 0.0f;
	positions[i * 3 + 0] = (float)slot;
	positions[i * 3 + 1] = y;
	positions[i * 3 + 2] = 2.5f * tanhf(changes[layer]);
}
"""

VERTEX_SHADER = """
#version 330 core
uniform mat4 osg_ModelViewProjectionMatrix;
uniform float latestSlot;
uniform float history;
in vec4 osg_Vertex;
out vec4 vColor;
void main(void) {
	float age = mod(latestSlot - osg_Vertex.x + history, history);
	float x = 5.0 - 10.0 * age / max(history - 1.0, 1.0);
	float activity = clamp(osg_Vertex.z / 2.5, 0.0, 1.0);
	gl_Position = osg_ModelViewProjectionMatrix * vec4(x, osg_Vertex.y, osg_Vertex.z, 1.0);
	vColor = mix(vec4(0.03, 0.10, 0.30, 1.0), vec4(1.0, 0.62, 0.04, 1.0), activity);
	gl_PointSize = 15.0;
}
"""

_model = None
_cuda = None
_latest_slot = None
_response = None
_stepper = None


def build_scene(w, h):
	global _model, _cuda, _latest_slot, _response, _stepper

	args = causal_lm_arguments("03 - render scrolling layer-change history through CUDA/GL interop")
	_model = CausalLMStepper(args.model, " ".join(args.prompt), args.max_new_tokens)
	_response = ResponseText(args.step)
	_stepper = TokenStepController(args.step, args.delay)
	point_count = HISTORY * _model.layers
	positions = osg.Vec3Array(point_count)
	geometry = osg.Geometry()

	geometry.vertexArray = positions
	geometry.primitiveSets.append(osg.DrawArrays(osg.PrimitiveSet.POINTS, 0, point_count))
	geometry.useVertexBufferObjects = True
	geometry.initialBound = osg.BoundingBox(-6, -4, -1, 6, 4, 3)

	geode = osg.Geode()

	geode.drawables.append(geometry)
	configure_glowing_points(geode, "Layer Change History", VERTEX_SHADER)
	_latest_slot = osg.Uniform("latestSlot", 0.0)
	geode.stateSet.uniforms.extend((_latest_slot, osg.Uniform("history", float(HISTORY))))
	_cuda = CUDAInteropVBO(positions, KERNEL_SOURCE, "writeLayerHistory")
	root = osg.Group()

	root.children.append(geode)
	root.children.append(_response.node)

	return root


def configure_viewer(viewer, root):
	slot = [0]
	initialized = [False]
	_stepper.install(viewer)

	def predraw(render_info):
		if not _cuda.try_register(render_info.contextID):
			return

		now = time.monotonic()

		if not _stepper.ready(now):
			return

		if _model.finished:
			return

		_, _, changes = _model.step()
		_cuda.launch_1d(
			HISTORY * _model.layers if not initialized[0] else _model.layers,
			ctypes.c_void_p(changes.data_ptr()),
			ctypes.c_int(_model.layers),
			ctypes.c_int(slot[0]),
			ctypes.c_int(HISTORY),
			ctypes.c_int(not initialized[0])
		)
		initialized[0] = True
		_latest_slot.value = float(slot[0])
		slot[0] = (slot[0] + 1) % HISTORY
		_response.push(_model.last_token_text)

		if _model.finished:
			_response.finish()

		_stepper.consume(now)

	viewer.camera.preDrawCallback = predraw
	print("Model says: ", end="", flush=True)


if __name__ == "__main__":
	W, H = window_size()
	viewer = osgViewer.Viewer()
	root = build_scene(W, H)

	viewer.sceneData = root
	viewer.cameraManipulator = osgGA.TrackballManipulator()
	configure_viewer(viewer, root)

	while not viewer.done:
		viewer.frame()
