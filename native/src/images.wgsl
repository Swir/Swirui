struct VertexInput {
    @location(0) position: vec2<f32>,
    @location(1) uv: vec2<f32>,
    @location(2) opacity: f32,
    @location(3) pixel_position: vec2<f32>,
    @location(4) clip: vec4<f32>,
};

struct VertexOutput {
    @builtin(position) position: vec4<f32>,
    @location(0) uv: vec2<f32>,
    @location(1) opacity: f32,
    @location(2) pixel_position: vec2<f32>,
    @location(3) @interpolate(flat) clip: vec4<f32>,
};

@group(0) @binding(0)
var image_texture: texture_2d<f32>;

@group(0) @binding(1)
var image_sampler: sampler;

@vertex
fn vs_main(input: VertexInput) -> VertexOutput {
    var output: VertexOutput;
    output.position = vec4<f32>(input.position, 0.0, 1.0);
    output.uv = input.uv;
    output.opacity = input.opacity;
    output.pixel_position = input.pixel_position;
    output.clip = input.clip;
    return output;
}

@fragment
fn fs_main(input: VertexOutput) -> @location(0) vec4<f32> {
    if (
        input.pixel_position.x < input.clip.x ||
        input.pixel_position.y < input.clip.y ||
        input.pixel_position.x > input.clip.z ||
        input.pixel_position.y > input.clip.w
    ) {
        discard;
    }
    let sampled = textureSample(image_texture, image_sampler, input.uv);
    return vec4<f32>(sampled.rgb, sampled.a * input.opacity);
}
