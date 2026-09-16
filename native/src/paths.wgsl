struct VertexInput {
    @location(0) position: vec2<f32>,
    @location(1) color: vec4<f32>,
    @location(2) clip_rect: vec4<f32>,
};

struct VertexOutput {
    @builtin(position) position: vec4<f32>,
    @location(0) color: vec4<f32>,
    @location(1) clip_rect: vec4<f32>,
};

@vertex
fn vs_main(input: VertexInput) -> VertexOutput {
    var output: VertexOutput;
    output.position = vec4<f32>(input.position, 0.0, 1.0);
    output.color = input.color;
    output.clip_rect = input.clip_rect;
    return output;
}

@fragment
fn fs_main(input: VertexOutput) -> @location(0) vec4<f32> {
    let pixel = input.position.xy;
    if (
        pixel.x < input.clip_rect.x ||
        pixel.y < input.clip_rect.y ||
        pixel.x >= input.clip_rect.z ||
        pixel.y >= input.clip_rect.w
    ) {
        discard;
    }
    return input.color;
}
