#!/usr/bin/env python3

"""02 - One relative RMS hidden-state change value per model layer."""

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


KERNEL_SOURCE = b"""
extern "C" __global__ void writeLayerChange(float* positions, const float* changes, int layers) {
	int layer = blockIdx.x * blockDim.x + threadIdx.x;

	if(layer >= layers) return;

	float x = layers > 1 ? 10.0f * layer / (layers - 1) - 5.0f : 0.0f;
	positions[layer * 3 + 0] = x;
	positions[layer * 3 + 1] = 0.0f;
	positions[layer * 3 + 2] = 3.0f * tanhf(changes[layer]);
}
"""

VERTEX_SHADER = """
#version 330 core
uniform mat4 osg_ModelViewProjectionMatrix;
in vec4 osg_Vertex;
out vec4 vColor;
void main(void) {
	float activity = clamp(osg_Vertex.z / 3.0, 0.0, 1.0);
	gl_Position = osg_ModelViewProjectionMatrix * osg_Vertex;
	vColor = mix(vec4(0.05, 0.18, 0.55, 1.0), vec4(1.0, 0.72, 0.08, 1.0), activity);
	gl_PointSize = 38.0;
}
"""

_model = None
_cuda = None
_response = None
_stepper = None


def build_scene(w, h):
	global _model, _cuda, _response, _stepper

	args = causal_lm_arguments("02 - render relative per-layer change through CUDA/GL interop")
	_model = CausalLMStepper(args.model, " ".join(args.prompt), args.max_new_tokens)
	_response = ResponseText(args.step)
	_stepper = TokenStepController(args.step, args.delay)
	positions = osg.Vec3Array(_model.layers)
	geometry = osg.Geometry()

	geometry.vertexArray = positions
	geometry.primitiveSets.append(osg.DrawArrays(osg.PrimitiveSet.POINTS, 0, _model.layers))
	geometry.useVertexBufferObjects = True
	geometry.initialBound = osg.BoundingBox(-6, -1, -1, 6, 1, 4)

	geode = osg.Geode()

	geode.drawables.append(geometry)
	configure_glowing_points(geode, "Layer Change", VERTEX_SHADER)
	_cuda = CUDAInteropVBO(positions, KERNEL_SOURCE, "writeLayerChange")
	root = osg.Group()

	root.children.append(geode)
	root.children.append(_response.node)

	return root


def configure_viewer(viewer, root):
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
			_model.layers,
			ctypes.c_void_p(changes.data_ptr()),
			ctypes.c_int(_model.layers)
		)
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
