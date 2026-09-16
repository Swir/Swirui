struct ImageUniforms {
    viewport: vec2<f32>,
    origin: vec2<f32>,
    size: vec2<f32>,
    opacity: f32,
    _padding: f32,
};

@group(0) @binding(0)
var<uniform> image: ImageUniforms;

@group(0) @binding(1)
var image_texture: texture_2d<f32>;

@group(0) @binding(2)
var image_sampler: sampler;

struct VertexOutput {
    @builtin(position) position: vec4<f32>,
    @location(0) uv: vec2<f32>,
};

@vertex
fn vs_main(@builtin(vertex_index) vertex_index: u32) -> VertexOutput {
    let corners = array<vec2<f32>, 6>(
        vec2<f32>(0.0, 0.0),
        vec2<f32>(1.0, 0.0),
        vec2<f32>(0.0, 1.0),
        vec2<f32>(0.0, 1.0),
        vec2<f32>(1.0, 0.0),
        vec2<f32>(1.0, 1.0),
    );
    let uv = corners[vertex_index];
    let pixel = image.origin + uv * image.size;
    let ndc = vec2<f32>(
        pixel.x / image.viewport.x * 2.0 - 1.0,
        1.0 - pixel.y / image.viewport.y * 2.0,
    );

    var output: VertexOutput;
    output.position = vec4<f32>(ndc, 0.0, 1.0);
    output.uv = uv;
    return output;
}

@fragment
fn fs_main(input: VertexOutput) -> @location(0) vec4<f32> {
    let sampled = textureSample(image_texture, image_sampler, input.uv);
    return vec4<f32>(sampled.rgb, sampled.a * image.opacity);
}
