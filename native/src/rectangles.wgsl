struct FrameUniforms {
    viewport: vec2<f32>,
    padding: vec2<f32>,
};

struct RectInstance {
    rect: vec4<f32>,
    color: vec4<f32>,
};

@group(0) @binding(0)
var<uniform> frame: FrameUniforms;

@group(0) @binding(1)
var<storage, read> rectangles: array<RectInstance>;

struct VertexOutput {
    @builtin(position) position: vec4<f32>,
    @location(0) color: vec4<f32>,
};

@vertex
fn vs_main(
    @builtin(vertex_index) vertex_index: u32,
    @builtin(instance_index) instance_index: u32,
) -> VertexOutput {
    let corners = array<vec2<f32>, 6>(
        vec2<f32>(0.0, 0.0),
        vec2<f32>(1.0, 0.0),
        vec2<f32>(0.0, 1.0),
        vec2<f32>(0.0, 1.0),
        vec2<f32>(1.0, 0.0),
        vec2<f32>(1.0, 1.0),
    );

    let item = rectangles[instance_index];
    let pixel = item.rect.xy + corners[vertex_index] * item.rect.zw;
    let ndc = vec2<f32>(
        (pixel.x / frame.viewport.x) * 2.0 - 1.0,
        1.0 - (pixel.y / frame.viewport.y) * 2.0,
    );

    var output: VertexOutput;
    output.position = vec4<f32>(ndc, 0.0, 1.0);
    output.color = item.color;
    return output;
}

@fragment
fn fs_main(input: VertexOutput) -> @location(0) vec4<f32> {
    return input.color;
}
