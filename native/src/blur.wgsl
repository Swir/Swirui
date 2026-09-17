@group(0) @binding(0)
var source_texture: texture_2d<f32>;

@group(0) @binding(1)
var source_sampler: sampler;

struct VertexOutput {
    @builtin(position) position: vec4<f32>,
    @location(0) uv: vec2<f32>,
}

@vertex
fn vs_main(@builtin(vertex_index) vertex_index: u32) -> VertexOutput {
    let positions = array<vec2<f32>, 3>(
        vec2<f32>(-1.0, -1.0),
        vec2<f32>(3.0, -1.0),
        vec2<f32>(-1.0, 3.0),
    );
    let position = positions[vertex_index];

    var output: VertexOutput;
    output.position = vec4<f32>(position, 0.0, 1.0);
    output.uv = position * vec2<f32>(0.5, -0.5) + vec2<f32>(0.5, 0.5);
    return output;
}

fn gaussian_sample(uv: vec2<f32>, direction: vec2<f32>) -> vec4<f32> {
    var color = textureSample(source_texture, source_sampler, uv) * 0.2270270270;
    color += textureSample(
        source_texture,
        source_sampler,
        uv + direction * 1.3846153846,
    ) * 0.3162162162;
    color += textureSample(
        source_texture,
        source_sampler,
        uv - direction * 1.3846153846,
    ) * 0.3162162162;
    color += textureSample(
        source_texture,
        source_sampler,
        uv + direction * 3.2307692308,
    ) * 0.0702702703;
    color += textureSample(
        source_texture,
        source_sampler,
        uv - direction * 3.2307692308,
    ) * 0.0702702703;
    return color;
}

@fragment
fn fs_horizontal(input: VertexOutput) -> @location(0) vec4<f32> {
    let dimensions = vec2<f32>(textureDimensions(source_texture));
    return gaussian_sample(input.uv, vec2<f32>(1.0 / dimensions.x, 0.0));
}

@fragment
fn fs_vertical(input: VertexOutput) -> @location(0) vec4<f32> {
    let dimensions = vec2<f32>(textureDimensions(source_texture));
    return gaussian_sample(input.uv, vec2<f32>(0.0, 1.0 / dimensions.y));
}
