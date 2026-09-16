struct ImageUniforms {
    surface_size: vec2<f32>,
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

fn quad_vertex(index: u32) -> vec2<f32> {
    let vertices = array<vec2<f32>, 6>(
        vec2<f32>(0.0, 0.0),
        vec2<f32>(1.0, 0.0),
        vec2<f32>(0.0, 1.0),
        vec2<f32>(0.0, 1.0),
        vec2<f32>(1.0, 0.0),
        vec2<f32>(1.0, 1.0),
    );
    return vertices[index];
}

@vertex
fn vs_main(@builtin(vertex_index) vertex_index: u32) -> VertexOutput {
    let unit = quad_vertex(vertex_index);
    let pixel = image.origin + unit * image.size;
    let normalized = vec2<f32>(
        pixel.x / image.surface_size.x * 2.0 - 1.0,
        1.0 - pixel.y / image.surface_size.y * 2.0,
    );

    var output: VertexOutput;
    output.position = vec4<f32>(normalized, 0.0, 1.0);
    output.uv = unit;
    return output;
}

@fragment
fn fs_main(input: VertexOutput) -> @location(0) vec4<f32> {
    let sampled = textureSample(image_texture, image_sampler, input.uv);
    return vec4<f32>(sampled.rgb, sampled.a * image.opacity);
}
