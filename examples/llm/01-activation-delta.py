#!/usr/bin/env python3

"""01 - The coordinate-by-coordinate hidden-state change since the preceding token."""

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
extern "C" __global__ void writeActivationDelta(float* positions, const float* delta,
	int channels, int layers) {
	int i = blockIdx.x * blockDim.x + threadIdx.x;
	int n = channels * layers;

	if(i >= n) return;

	int layer = i / channels;
	int channel = i - layer * channels;
	float x = channels > 1 ? 10.0f * channel / (channels - 1) - 5.0f : 0.0f;
	float y = layers > 1 ? 6.0f * layer / (layers - 1) - 3.0f : 0.0f;

	positions[i * 3 + 0] = x;
	positions[i * 3 + 1] = y;
	positions[i * 3 + 2] = 3.0f * tanhf(4.0f * delta[i]);
}
"""

VERTEX_SHADER = """
#version 330 core
uniform mat4 osg_ModelViewProjectionMatrix;
in vec4 osg_Vertex;
out vec4 vColor;
void main(void) {
	float magnitude = clamp(abs(osg_Vertex.z) / 3.0, 0.06, 1.0);
	gl_Position = osg_ModelViewProjectionMatrix * osg_Vertex;
	vColor = osg_Vertex.z >= 0.0 ? vec4(1.0, 0.25, 0.04, 1.0) * magnitude
		: vec4(0.04, 0.40, 1.0, 1.0) * magnitude;
	gl_PointSize = 14.0;
}
"""

_model = None
_cuda = None
_response = None
_stepper = None


def build_scene(w, h):
	global _model, _cuda, _response, _stepper

	args = causal_lm_arguments("01 - render hidden-state deltas through CUDA/GL interop")
	_model = CausalLMStepper(args.model, " ".join(args.prompt), args.max_new_tokens)
	_response = ResponseText(args.step)
	_stepper = TokenStepController(args.step, args.delay)
	point_count = _model.layers * _model.channels
	positions = osg.Vec3Array(point_count)
	geometry = osg.Geometry()

	geometry.vertexArray = positions
	geometry.primitiveSets.append(osg.DrawArrays(osg.PrimitiveSet.POINTS, 0, point_count))
	geometry.useVertexBufferObjects = True
	geometry.initialBound = osg.BoundingBox(-6, -4, -4, 6, 4, 4)

	geode = osg.Geode()

	geode.drawables.append(geometry)
	configure_glowing_points(geode, "Activation Delta", VERTEX_SHADER)
	_cuda = CUDAInteropVBO(positions, KERNEL_SOURCE, "writeActivationDelta")
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

		_, delta, _ = _model.step()
		_cuda.launch_1d(
			_model.layers * _model.channels,
			ctypes.c_void_p(delta.data_ptr()),
			ctypes.c_int(_model.channels),
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
