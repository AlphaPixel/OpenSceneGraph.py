"""Shared Qwen and CUDA/GL plumbing for the sequential LLM examples.

The numbered examples deliberately keep their CUDA kernels and rendering code local. This module
contains only the setup which is unrelated to the visualization being taught.
"""

import argparse
import ctypes
import sys
from collections import deque
from math import pi

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from OpenSceneGraph import osg, osgGA
from OpenSceneGraph.GL import *

import osgx

from cuda.bindings import driver, nvrtc


GLOWING_POINT_FRAGMENT_SHADER = """
#version 330 core
in vec4 vColor;
out vec4 color;
void main(void) {
	vec2 p = gl_PointCoord * 2.0 - 1.0;
	float alpha = exp(-dot(p, p) * 3.0);
	color = vec4(vColor.rgb, alpha);
}
"""


def configure_glowing_points(geode, name, vertex_shader):
	"""Install the shared additive point-cloud rendering used by every LLM lesson."""
	geode.stateSet.modes[GL_PROGRAM_POINT_SIZE] = osg.StateAttribute.Values.ON
	geode.stateSet.modes[GL_VERTEX_PROGRAM_POINT_SIZE] = osg.StateAttribute.Values.ON
	geode.stateSet.modes[GL_BLEND] = osg.StateAttribute.Values.ON
	geode.stateSet.attributes.append(osg.Program(name=name, shaders=(
		osg.Shader(osg.Shader.VERTEX, vertex_shader),
		osg.Shader(osg.Shader.FRAGMENT, GLOWING_POINT_FRAGMENT_SHADER)
	)))
	geode.stateSet.attributes[osg.StateAttribute.BLENDFUNC] = (
		osg.BlendFunc(GL_SRC_ALPHA, GL_ONE), osg.StateAttribute.Values.ON
	)
	geode.stateSet.attributes[osg.StateAttribute.DEPTH] = (
		osg.Depth(osg.Depth.LESS, 0.0, 1.0, False), osg.StateAttribute.Values.ON
	)
	geode.stateSet.renderingHint = osg.StateSet.TRANSPARENT_BIN


class ResponseText:
	"""A deliberately in-scene, non-billboarded view of Qwen's recent token text."""
	LINE_WIDTH = 34
	TOKEN_COUNT = 10

	def __init__(self, step_mode):
		self.tokens = deque(maxlen=self.TOKEN_COUNT)
		self.labels = []
		self.node = osg.Group(name="Qwen response text")
		rotation = osg.Matrix.rotate(0.5 * pi, osg.Vec3(1.0, 0.0, 0.0))

		for line in range(3):
			label = osgx.PixelText("", 0.16)
			geode = osg.Geode(name=f"Qwen response line {line}")
			transform = osg.MatrixTransform(
				rotation * osg.Matrix.translate(-4.8, -3.4, 3.2 - 0.28 * line)
			)

			label.ink = osg.Vec4(1.0, 0.78 if line == 0 else 0.95, 0.16 if line == 0 else 1.0, 1.0)
			geode.drawables.append(label)
			transform.children.append(geode)
			self.node.children.append(transform)
			self.labels.append(label)

		self.labels[0].text = "LAST 10 - N NEXT" if step_mode else "LAST 10 TOKENS"

	def push(self, token_text):
		self.tokens.append(token_text)
		text = self._pixel_text("".join(self.tokens))[-2 * self.LINE_WIDTH:]

		self.labels[1].text = text[:self.LINE_WIDTH]
		self.labels[2].text = text[self.LINE_WIDTH:]

	def finish(self):
		self.labels[0].text = "END OF RESPONSE"

	@staticmethod
	def _pixel_text(text):
		charset = set(osgx.PixelText.CHARSET)
		result = []

		for character in text:
			if character in ("\n", "\r"):
				continue

			uppercase = character.upper()
			result.append(uppercase if len(uppercase) == 1 and uppercase in charset else "?")

		return "".join(result)


class TokenStepController(osgGA.GUIEventHandler):
	"""Queue exactly one Qwen inference step for each N key release."""
	def __init__(self, step_mode, delay):
		super().__init__()
		self.step_mode = step_mode
		self.delay = delay
		self.pending = False
		self.last_step = 0.0

	def handle(self, event, action_adapter):
		if not self.step_mode or event.handled or event.type != osgGA.GUIEventAdapter.KEYUP:
			return False

		if event.key not in (ord("n"), ord("N")):
			return False

		self.pending = True

		return True

	def install(self, viewer):
		if self.step_mode:
			viewer.eventHandlers.append(self)
			print("Qwen: press N for the next token")

	def ready(self, now):
		return self.pending if self.step_mode else now - self.last_step >= self.delay

	def consume(self, now):
		self.pending = False
		self.last_step = now


def cu(result):
	code = result[0] if isinstance(result, tuple) else result

	if int(code) != 0:
		raise RuntimeError(f"CUDA error: {code}")

	if isinstance(result, tuple):
		rest = result[1:]

		return rest[0] if len(rest) == 1 else rest


def qwen_arguments(description):
	parser = argparse.ArgumentParser(description=description)
	parser.add_argument("--model", required=True, help="local Hugging Face model checkout")
	parser.add_argument(
		"--max-new-tokens",
		type=int,
		default=256,
		help="safety limit when the model does not emit EOS (default: 256)"
	)
	parser.add_argument(
		"--delay",
		type=float,
		default=0.5,
		help="seconds between generated tokens; 0 runs without artificial pacing"
	)
	parser.add_argument(
		"--step",
		action="store_true",
		help="generate only when N is released"
	)
	parser.add_argument("prompt", nargs="+", help="prompt passed to Qwen")

	return parser.parse_args()


class QwenStepper:
	"""Generate one token at a time and retain all activation-derived data in VRAM."""
	def __init__(self, model_path, prompt, max_new_tokens=256):
		if max_new_tokens < 1:
			raise ValueError("max_new_tokens must be positive")

		self.tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
		self.model = AutoModelForCausalLM.from_pretrained(
			model_path,
			dtype=torch.float16,
			local_files_only=True
		).to("cuda").eval()
		text = self.tokenizer.apply_chat_template(
			[{"role": "user", "content": prompt}],
			tokenize=False,
			add_generation_prompt=True
		)
		self.input_ids = self.tokenizer(text, return_tensors="pt").input_ids.to("cuda")
		self.past_key_values = None
		self.layers = self.model.config.num_hidden_layers + 1
		self.channels = self.model.config.hidden_size
		self.previous = None
		self.generated_tokens = 0
		self.max_new_tokens = max_new_tokens
		self.eos_token_ids = set()
		generation_eos = getattr(self.model.generation_config, "eos_token_id", None)

		if self.tokenizer.eos_token_id is not None:
			self.eos_token_ids.add(self.tokenizer.eos_token_id)

		if isinstance(generation_eos, (list, tuple)):
			self.eos_token_ids.update(generation_eos)
		elif generation_eos is not None:
			self.eos_token_ids.add(generation_eos)

		self.finished = False

		print(f"Qwen: {self.layers} state rows x {self.channels} channels")

	def step(self):
		if self.finished:
			return None

		with torch.inference_mode():
			output = self.model(
				input_ids=self.input_ids,
				past_key_values=self.past_key_values,
				use_cache=True,
				output_hidden_states=True,
				return_dict=True
			)

		self.past_key_values = output.past_key_values
		activation = torch.stack([state[0, -1] for state in output.hidden_states]).float().contiguous()
		next_token = torch.argmax(output.logits[:, -1, :], dim=-1, keepdim=True)
		self.input_ids = next_token
		next_token_id = int(next_token.item())
		self.generated_tokens += 1
		self.last_token_text = self.tokenizer.decode(next_token[0], skip_special_tokens=True)

		if self.previous is None:
			delta = torch.zeros_like(activation)

		else:
			delta = (activation - self.previous).contiguous()

		# Holding this CUDA tensor is the only temporal state required by lesson 01.
		self.previous = activation
		layer_change = delta.square().mean(dim=1).sqrt().contiguous()
		relative_layer_change = (layer_change / layer_change.mean().clamp_min(1.0e-6)).contiguous()

		# This decode is only terminal output. Activation data never traverses the CPU.
		print(self.last_token_text, end="", flush=True)

		if next_token_id in self.eos_token_ids:
			self.finished = True
			print("\n[Qwen: end of response]", flush=True)

		elif self.generated_tokens >= self.max_new_tokens:
			self.finished = True
			print("\n[Qwen: reached --max-new-tokens]", flush=True)

		return activation, delta, relative_layer_change


class CUDAInteropVBO:
	"""Compile one example-local kernel and let it write directly into an OSG VBO."""
	def __init__(self, array, kernel_source, kernel_name):
		self.array = array
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
		self.context = cu(driver.cuDevicePrimaryCtxRetain(device))
		self._push()

		try:
			program = cu(nvrtc.nvrtcCreateProgram(kernel_source, kernel_name.encode(), 0, [], []))
			options = [f"--gpu-architecture=compute_{major}{minor}".encode()]
			compile_result = nvrtc.nvrtcCompileProgram(program, len(options), options)
			log_size = cu(nvrtc.nvrtcGetProgramLogSize(program))
			log = bytearray(log_size)

			nvrtc.nvrtcGetProgramLog(program, log)

			if int(compile_result[0]) != 0:
				sys.exit(f"NVRTC compile failed:\n{bytes(log).decode()}")

			ptx_size = cu(nvrtc.nvrtcGetPTXSize(program))
			ptx = bytearray(ptx_size)

			nvrtc.nvrtcGetPTX(program, ptx)
			self.module = cu(driver.cuModuleLoadData(bytes(ptx)))
			self.function = cu(driver.cuModuleGetFunction(self.module, kernel_name.encode()))
		finally:
			self._pop()

	def _push(self):
		cu(driver.cuCtxPushCurrent(self.context))

	def _pop(self):
		cu(driver.cuCtxPopCurrent())

	def try_register(self, context_id):
		if self.resource is not None:
			return True

		buffer_object = self.array.bufferObject

		if buffer_object is None:
			return False

		gl_buffer = buffer_object.glBufferObject(context_id)

		if gl_buffer.glObjectID == 0:
			return False

		self._push()

		try:
			self.resource = cu(driver.cuGraphicsGLRegisterBuffer(
				gl_buffer.glObjectID,
				driver.CUgraphicsRegisterFlags.CU_GRAPHICS_REGISTER_FLAGS_NONE
			))
		finally:
			self._pop()

		print(f"CUDA: registered GL buffer {gl_buffer.glObjectID} (contextID={context_id})")

		return True

	def launch_1d(self, count, *values):
		"""Pass the mapped position pointer followed by CUDA scalar/pointer arguments."""
		torch.cuda.synchronize()
		self._push()

		try:
			cu(driver.cuGraphicsMapResources(1, self.resource, 0))

			try:
				positions, _ = cu(driver.cuGraphicsResourceGetMappedPointer(self.resource))
				position_arg = ctypes.c_void_p(int(positions))
				arguments = (position_arg, *values)
				args = (ctypes.c_void_p * len(arguments))()

				for i, value in enumerate(arguments):
					args[i] = ctypes.cast(ctypes.pointer(value), ctypes.c_void_p)

				block = 256
				grid = (count + block - 1) // block
				cu(driver.cuLaunchKernel(self.function, grid, 1, 1, block, 1, 1, 0, 0, args, 0))
			finally:
				cu(driver.cuGraphicsUnmapResources(1, self.resource, 0))
		finally:
			self._pop()
