struct BlurParams {
    direction: vec2<f32>,
    _padding: vec2<f32>,
}

@group(0) @binding(0)
var source_texture: texture_2d<f32>;

@group(0) @binding(1)
var source_sampler: sampler;

@group(0) @binding(2)
var<uniform> params: BlurParams;

struct VertexOutput {
    @builtin(position) position: vec4<f32>,
    @location(0) uv: vec2<f32>,
}

@vertex
fn vs_main(@builtin(vertex_index) vertex_index: u32) -> VertexOutput {
    var positions = array<vec2<f32>, 3>(
        vec2<f32>(-1.0, -3.0),
        vec2<f32>(-1.0, 1.0),
        vec2<f32>(3.0, 1.0),
    );
    var uvs = array<vec2<f32>, 3>(
        vec2<f32>(0.0, 2.0),
        vec2<f32>(0.0, 0.0),
        vec2<f32>(2.0, 0.0),
    );

    var output: VertexOutput;
    output.position = vec4<f32>(positions[vertex_index], 0.0, 1.0);
    output.uv = uvs[vertex_index];
    return output;
}

@fragment
fn fs_main(input: VertexOutput) -> @location(0) vec4<f32> {
    var color = textureSample(source_texture, source_sampler, input.uv) * 0.2270270270;
    color += textureSample(
        source_texture,
        source_sampler,
        input.uv + params.direction * 1.3846153846,
    ) * 0.3162162162;
    color += textureSample(
        source_texture,
        source_sampler,
        input.uv - params.direction * 1.3846153846,
    ) * 0.3162162162;
    color += textureSample(
        source_texture,
        source_sampler,
        input.uv + params.direction * 3.2307692308,
    ) * 0.0702702703;
    color += textureSample(
        source_texture,
        source_sampler,
        input.uv - params.direction * 3.2307692308,
    ) * 0.0702702703;
    return color;
}
