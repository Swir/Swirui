struct FrameUniforms {
    size: vec2<f32>,
    _padding: vec2<f32>,
}

@group(0) @binding(0)
var<uniform> frame: FrameUniforms;

struct VertexInput {
    @location(0) position: vec2<f32>,
    @location(1) color: vec4<f32>,
    @location(2) clip: vec4<f32>,
}

struct VertexOutput {
    @builtin(position) clip_position: vec4<f32>,
    @location(0) color: vec4<f32>,
    @location(1) pixel_position: vec2<f32>,
    @location(2) @interpolate(flat) clip: vec4<f32>,
}

@vertex
fn vs_main(input: VertexInput) -> VertexOutput {
    var output: VertexOutput;
    let safe_size = max(frame.size, vec2<f32>(1.0, 1.0));
    let ndc = vec2<f32>(
        input.position.x / safe_size.x * 2.0 - 1.0,
        1.0 - input.position.y / safe_size.y * 2.0,
    );
    output.clip_position = vec4<f32>(ndc, 0.0, 1.0);
    output.color = input.color;
    output.pixel_position = input.position;
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
    return input.color;
}
