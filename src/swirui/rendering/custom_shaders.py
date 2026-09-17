"""Safe Python-first contract for user-defined SwirUI post-process shaders.

The first custom-shader API deliberately exposes a bounded pure-function WGSL
contract instead of arbitrary GPU bindings. User code receives the already
rendered color, normalized UV coordinates and one vec4 parameter block, then
returns a replacement RGBA color. SwirUI owns the texture/sampler bindings,
fullscreen vertex stage and presentation fragment entry point.

This conservative boundary keeps the public API useful while preventing custom
effects from declaring storage buffers, workgroup state, additional entry
points or unbounded loops. The composed shader can additionally be validated by
the native Naga validator before a future renderer pipeline is created.
"""

from __future__ import annotations

import hashlib
import importlib
import math
import re
from dataclasses import dataclass, replace
from typing import Any

ShaderParameters = tuple[float, float, float, float]

_MAX_SOURCE_BYTES = 32 * 1024
_MAX_LABEL_LENGTH = 64
_EFFECT_SIGNATURE = re.compile(
    r"\bfn\s+swirui_effect\s*\(\s*"
    r"color\s*:\s*vec4\s*<\s*f32\s*>\s*,\s*"
    r"uv\s*:\s*vec2\s*<\s*f32\s*>\s*,\s*"
    r"params\s*:\s*vec4\s*<\s*f32\s*>\s*"
    r"\)\s*->\s*vec4\s*<\s*f32\s*>",
    re.MULTILINE,
)
_LABEL_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9 _.\-]{0,63}\Z")
_FORBIDDEN_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"@"), "WGSL attributes are owned by SwirUI"),
    (re.compile(r"\bvar\s*<"), "address-space variables are not allowed"),
    (re.compile(r"\batomic\s*<"), "atomics are not allowed"),
    (
        re.compile(r"\btexture_[A-Za-z0-9_]*"),
        "texture declarations/operations are not allowed",
    ),
    (re.compile(r"\bsampler\b"), "sampler declarations are not allowed"),
    (
        re.compile(r"\bworkgroup[A-Za-z0-9_]*\b"),
        "workgroup operations are not allowed",
    ),
    (re.compile(r"\bstorageBarrier\s*\("), "storage barriers are not allowed"),
    (re.compile(r"\bloop\b"), "unbounded loops are not allowed"),
    (re.compile(r"\bwhile\b"), "while loops are not allowed"),
    (
        re.compile(r"\bfor\b"),
        "for loops are not allowed in the initial shader contract",
    ),
)
_RESERVED_SYMBOLS = (
    "SwirUiVertexOutput",
    "SwirUiEffectParams",
    "swirui_source_texture",
    "swirui_source_sampler",
    "swirui_effect_params",
    "vs_main",
    "fs_main",
)


@dataclass(frozen=True, slots=True)
class CustomShaderEffect:
    """A bounded custom WGSL color transform owned by the Python public API.

    ``source`` must define exactly one function with this interface::

        fn swirui_effect(
            color: vec4<f32>,
            uv: vec2<f32>,
            params: vec4<f32>,
        ) -> vec4<f32>

    The source may contain helper functions and constants, but it cannot declare
    bindings, shader entry points, storage/workgroup state, texture access or
    loops. ``parameters`` is a four-float uniform value that can change without
    changing the shader's pipeline key.
    """

    source: str
    parameters: ShaderParameters = (0.0, 0.0, 0.0, 0.0)
    label: str = "custom-effect"

    def __post_init__(self) -> None:
        self._validate_label(self.label)
        self._validate_source(self.source)
        self._validate_parameters(self.parameters)

    @property
    def pipeline_key(self) -> str:
        """Stable source-only key suitable for persistent native pipeline caches."""

        digest = hashlib.sha256(self.native_wgsl().encode("utf-8"))
        return digest.hexdigest()

    @property
    def state_key(self) -> str:
        """Stable key covering both compiled shader source and current parameters."""

        digest = hashlib.sha256(self.pipeline_key.encode("ascii"))
        for value in self.parameters:
            digest.update(value.hex().encode("ascii"))
            digest.update(b";")
        return digest.hexdigest()

    def with_parameters(self, *values: float) -> CustomShaderEffect:
        """Return the same compiled effect contract with a new vec4 parameter block."""

        if len(values) != 4:
            raise ValueError("Custom shader parameters require exactly four float values.")
        parameters: ShaderParameters = (
            float(values[0]),
            float(values[1]),
            float(values[2]),
            float(values[3]),
        )
        return replace(self, parameters=parameters)

    def native_parameters(self) -> ShaderParameters:
        """Return the parameter block in deterministic PyO3-friendly order."""

        return self.parameters

    def native_wgsl(self) -> str:
        """Compose the restricted user function into SwirUI's owned GPU interface."""

        return f"""struct SwirUiVertexOutput {{
    @builtin(position) position: vec4<f32>,
    @location(0) uv: vec2<f32>,
}}

struct SwirUiEffectParams {{
    values: vec4<f32>,
}}

@group(0) @binding(0)
var swirui_source_texture: texture_2d<f32>;

@group(0) @binding(1)
var swirui_source_sampler: sampler;

@group(0) @binding(2)
var<uniform> swirui_effect_params: SwirUiEffectParams;

@vertex
fn vs_main(@builtin(vertex_index) vertex_index: u32) -> SwirUiVertexOutput {{
    var positions = array<vec2<f32>, 3>(
        vec2<f32>(-1.0, -3.0),
        vec2<f32>(3.0, 1.0),
        vec2<f32>(-1.0, 1.0),
    );
    var uvs = array<vec2<f32>, 3>(
        vec2<f32>(0.0, 2.0),
        vec2<f32>(2.0, 0.0),
        vec2<f32>(0.0, 0.0),
    );
    var output: SwirUiVertexOutput;
    output.position = vec4<f32>(positions[vertex_index], 0.0, 1.0);
    output.uv = uvs[vertex_index];
    return output;
}}

{self.source.strip()}

@fragment
fn fs_main(input: SwirUiVertexOutput) -> @location(0) vec4<f32> {{
    let color = textureSample(swirui_source_texture, swirui_source_sampler, input.uv);
    return swirui_effect(color, input.uv, swirui_effect_params.values);
}}
"""

    def validate_native(self, native_module: Any | None = None) -> None:
        """Run the composed WGSL through the native Naga parser and validator.

        The native extension is optional for ordinary Python-side construction.
        Calling this method without an injected module requires the Maturin-built
        ``_swirui_native`` extension to be installed.
        """

        module = native_module
        if module is None:
            try:
                module = importlib.import_module("_swirui_native")
            except ImportError as exc:
                raise RuntimeError(
                    "Native custom shader validation requires the SwirUI "
                    "Maturin extension."
                ) from exc
        validate = getattr(module, "validate_custom_shader_wgsl", None)
        if validate is None:
            raise RuntimeError(
                "Installed SwirUI native core does not expose custom shader "
                "WGSL validation."
            )
        validate(self.native_wgsl())

    @staticmethod
    def _validate_label(label: str) -> None:
        valid = (
            bool(label)
            and len(label) <= _MAX_LABEL_LENGTH
            and _LABEL_PATTERN.fullmatch(label) is not None
        )
        if not valid:
            raise ValueError(
                "Custom shader label must be 1-64 characters using letters, "
                "numbers, spaces, ., _ or -."
            )

    @staticmethod
    def _validate_parameters(parameters: ShaderParameters) -> None:
        if len(parameters) != 4:
            raise ValueError("Custom shader parameters require exactly four float values.")
        if not all(math.isfinite(value) for value in parameters):
            raise ValueError("Custom shader parameters must be finite.")

    @staticmethod
    def _validate_source(source: str) -> None:
        if not source.strip():
            raise ValueError("Custom shader source cannot be empty.")
        if "\x00" in source:
            raise ValueError("Custom shader source cannot contain NUL characters.")
        if len(source.encode("utf-8")) > _MAX_SOURCE_BYTES:
            raise ValueError("Custom shader source cannot exceed 32 KiB.")
        if len(re.findall(r"\bfn\s+swirui_effect\b", source)) != 1:
            raise ValueError(
                "Custom shader source must define exactly one swirui_effect function."
            )
        if _EFFECT_SIGNATURE.search(source) is None:
            raise ValueError(
                "swirui_effect must accept (color: vec4<f32>, uv: vec2<f32>, "
                "params: vec4<f32>) and return vec4<f32>."
            )
        for pattern, reason in _FORBIDDEN_PATTERNS:
            if pattern.search(source) is not None:
                raise ValueError(
                    f"Custom shader source is outside the safe contract: {reason}."
                )
        for symbol in _RESERVED_SYMBOLS:
            if re.search(rf"\b{re.escape(symbol)}\b", source) is not None:
                raise ValueError(
                    f"Custom shader source uses reserved SwirUI symbol {symbol!r}."
                )
