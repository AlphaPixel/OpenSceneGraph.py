#!/usr/bin/env python3
#vimrun! python3 ../examples/pyosg-cuda-points.py

import ctypes
import os
import struct
import sys
import time

os.environ.update({
	"OSG_WINDOW": "50 50 800 600",
	"OSG_THREADING": "SingleThreaded",
	"OSG_GL_CONTEXT_PROFILE_MASK": "1",
	"OSG_GL_VERSION": "4.6",
	"OSG_GL_CONTEXT_VERSION": "4.6"
})

from OpenSceneGraph import *
from OpenSceneGraph.GL import *

from cuda.bindings import driver, nvrtc

# The proof: a CUDA kernel writes point positions directly into the SAME GL buffer OSG
# renders from, every frame, with zero CPU involvement in that data. No NumPy array, no
# def_buffer() host pointer, no readback -- the CPU only ever passes a single scalar (the
# current time) as a kernel launch parameter, exactly like a GLSL uniform. This is the
# "GPU-resident LLM data, no CPU roundtrip" story from ai/context-todo-cuda-gpu-interop.md,
# in its smallest possible form: swap KERNEL for "an LLM's output tensor" and this is the
# whole mechanism.
#
# Chain used: osg.Vec3Array.bufferObject -> osg.BufferObject.glBufferObject(contextID)
# -> osg.GLBufferObject.glObjectID (added to OpenSceneGraph.py itself this session) is the
# raw GL buffer name CUDA's cuGraphicsGLRegisterBuffer() needs to register the SAME memory.
#
# Uses NVRTC (in-process kernel compilation, via the `cuda-python` pip wheel) instead of a
# system CUDA toolkit -- nvcc is not required to run this.

POINT_COUNT = 2000

KERNEL_SOURCE = b"""
extern "C" __global__ void animateSpiral(float* pos, int n, float t) {
	int i = blockIdx.x * blockDim.x + threadIdx.x;

	if(i >= n) return;

	float a = 0.15f * i + t;
	float r = 0.003f * i;

	pos[i * 3 + 0] = r * cosf(a);
	pos[i * 3 + 1] = r * sinf(a);
	pos[i * 3 + 2] = 0.4f * sinf(0.5f * t + 0.05f * i);
}
"""

VERTEX_SHADER = """
#version 330 core

uniform mat4 osg_ModelViewProjectionMatrix;

in vec4 osg_Vertex;
out vec4 vColor;

void main(void) {
	gl_Position = osg_ModelViewProjectionMatrix * osg_Vertex;
	vColor = vec4(1.0, 0.55, 0.1, 1.0);
	gl_PointSize = 8.0;
}
"""

FRAGMENT_SHADER = """
#version 330 core

in vec4 vColor;
out vec4 color;

void main(void) {
	vec2 p = gl_PointCoord * 2.0 - 1.0;
	float r2 = dot(p, p);
	float glow = exp(-r2 * 3.0);

	color = vec4(vColor.rgb, vColor.a * glow);
}
"""

def cu(result):
	code = result[0] if isinstance(result, tuple) else result

	if int(code) != 0:
		raise RuntimeError(f"CUDA error: {code}")

	if isinstance(result, tuple):
		rest = result[1:]

		return rest[0] if len(rest) == 1 else rest


class CUDAPointDriver:
	def __init__(self, array, point_count):
		self.array = array
		self.point_count = point_count
		self.resource = None

		cu(driver.cuInit(0))

		device = cu(driver.cuDeviceGet(0))
		major = cu(driver.cuDeviceGetAttribute(
			driver.CUdevice_attribute.CU_DEVICE_ATTRIBUTE_COMPUTE_CAPABILITY_MAJOR,
			device
		))
		minor = cu(driver.cuDeviceGetAttribute(
			driver.CUdevice_attribute.CU_DEVICE_ATTRIBUTE_COMPUTE_CAPABILITY_MINOR,
			device
		))
		self.compute_capability = f"compute_{major}{minor}"

		# CUDA Python 12 returns a context from cuCtxCreate(flags, device), while
		# CUDA Python 13 retains the C output-parameter-shaped binding. Support
		# both so the demo can use CUDA 12 on Pascal as well as newer toolkits.
		try:
			self.context = cu(driver.cuCtxCreate(0, device))
		except TypeError:
			self.context = cu(driver.cuCtxCreate(None, 0, device))

		program = cu(nvrtc.nvrtcCreateProgram(KERNEL_SOURCE, b"animateSpiral.cu", 0, [], []))
		# Never rely on NVRTC's default virtual architecture: compile for the
		# actual device, so Pascal (compute_61) and newer GPUs each receive PTX
		# their driver can JIT. CUDA 13 intentionally rejects pre-Turing targets;
		# CUDA 12.x remains the compatible compiler choice for those older GPUs.
		compile_options = [f"--gpu-architecture={self.compute_capability}".encode()]
		compile_result = nvrtc.nvrtcCompileProgram(program, len(compile_options), compile_options)

		log_size = cu(nvrtc.nvrtcGetProgramLogSize(program))
		log = bytearray(log_size)

		nvrtc.nvrtcGetProgramLog(program, log)

		if int(compile_result[0]) != 0:
			sys.exit(f"NVRTC compile failed:\\n{bytes(log).decode()}")

		ptx_size = cu(nvrtc.nvrtcGetPTXSize(program))
		ptx = bytearray(ptx_size)

		nvrtc.nvrtcGetPTX(program, ptx)

		module = cu(driver.cuModuleLoadData(bytes(ptx)))

		self.function = cu(driver.cuModuleGetFunction(module, b"animateSpiral"))

	# Registration can only happen once OSG has actually compiled a real GL buffer for the
	# array (glObjectID reads 0 until then) -- this quietly retries every frame until that's
	# true, then registers exactly once.
	def try_register(self, context_id):
		if self.resource is not None:
			return True

		buffer_object = self.array.bufferObject

		if buffer_object is None:
			return False

		gl_buffer = buffer_object.glBufferObject(context_id)

		if gl_buffer.glObjectID == 0:
			return False

		self.resource = cu(driver.cuGraphicsGLRegisterBuffer(
			gl_buffer.glObjectID,
			driver.CUgraphicsRegisterFlags.CU_GRAPHICS_REGISTER_FLAGS_NONE
		))

		print(f"CUDA: registered GL buffer {gl_buffer.glObjectID} (contextID={context_id})")

		return True

	def step(self, sim_time, verbose=False):
		cu(driver.cuGraphicsMapResources(1, self.resource, 0))

		device_ptr, size = cu(driver.cuGraphicsResourceGetMappedPointer(self.resource))

		n_arg = ctypes.c_int(self.point_count)
		t_arg = ctypes.c_float(sim_time)
		ptr_arg = ctypes.c_void_p(int(device_ptr))

		args = (ctypes.c_void_p * 3)()

		args[0] = ctypes.cast(ctypes.pointer(ptr_arg), ctypes.c_void_p)
		args[1] = ctypes.cast(ctypes.pointer(n_arg), ctypes.c_void_p)
		args[2] = ctypes.cast(ctypes.pointer(t_arg), ctypes.c_void_p)

		block = 256
		grid = (self.point_count + block - 1) // block

		cu(driver.cuLaunchKernel(self.function, grid, 1, 1, block, 1, 1, 0, 0, args, 0))

		# Diagnostic-only verification, NOT part of the render path: proves the kernel is
		# actually writing new values each call, without which this would be unverifiable
		# from a screenshot alone. Reads while still mapped -- reading after unmap is
		# undefined per the CUDA/GL interop contract.
		if verbose:
			cu(driver.cuCtxSynchronize())

			host = bytearray(12)

			cu(driver.cuMemcpyDtoH(host, device_ptr, 12))

			x, y, z = struct.unpack("3f", bytes(host))

			print(f"  t={sim_time:6.2f}  point[0]=({x:+.4f}, {y:+.4f}, {z:+.4f})")

		cu(driver.cuGraphicsUnmapResources(1, self.resource, 0))


if __name__ == "__main__":
	osg.setNotifyLevel(osg.NotifySeverity.NOTICE)

	positions = osg.Vec3Array(POINT_COUNT)

	g = osg.Geometry()

	g.vertexArray = positions
	g.primitiveSets.append(osg.DrawArrays(osg.PrimitiveSet.POINTS, 0, POINT_COUNT))
	g.useVertexBufferObjects = True
	g.initialBound = osg.BoundingBox(-6, -6, -6, 6, 6, 6)

	r = osg.Geode()

	r.drawables.append(g)
	r.stateSet.setMode(GL_PROGRAM_POINT_SIZE, osg.StateAttribute.Values.ON)
	r.stateSet.setMode(GL_VERTEX_PROGRAM_POINT_SIZE, osg.StateAttribute.Values.ON)
	r.stateSet.setMode(GL_BLEND, osg.StateAttribute.Values.ON)
	r.stateSet.attributes.append(osg.Program(name="CUDA Points DEMO", shaders=(
		osg.Shader(osg.Shader.VERTEX, VERTEX_SHADER),
		osg.Shader(osg.Shader.FRAGMENT, FRAGMENT_SHADER)
	)))
	r.stateSet.attributes[osg.StateAttribute.BLENDFUNC] = (
		osg.BlendFunc(GL_SRC_ALPHA, GL_ONE),
		osg.StateAttribute.Values.ON
	)

	cuda_driver = CUDAPointDriver(positions, POINT_COUNT)
	frame_index = [0]

	def predraw(ri):
		if not cuda_driver.try_register(ri.contextID):
			return

		frame_index[0] += 1

		verbose = (frame_index[0] % 60 == 1)

		cuda_driver.step(ri.state.frameStamp.simulationTime, verbose=verbose)

	v = osgViewer.Viewer()

	v.sceneData = r
	v.cameraManipulator = osgGA.TrackballManipulator()
	v.camera.preDrawCallback = predraw

	while not v.done:
		v.frame()

		time.sleep(0.01)
