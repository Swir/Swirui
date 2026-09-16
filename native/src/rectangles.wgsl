struct FrameUniforms {
    viewport: vec2<f32>,
    padding: vec2<f32>,
};

struct RectInstance {
    rect: vec4<f32>,
    color: vec4<f32>,
    radii: vec4<f32>,
};

@group(0) @binding(0)
var<uniform> frame: FrameUniforms;

@group(0) @binding(1)
var<storage, read> rectangles: array<RectInstance>;

struct VertexOutput {
    @builtin(position) position: vec4<f32>,
    @location(0) color: vec4<f32>,
    @location(1) local: vec2<f32>,
    @location(2) size: vec2<f32>,
    @location(3) radii: vec4<f32>,
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
    let local = corners[vertex_index] * item.rect.zw;
    let pixel = item.rect.xy + local;
    let ndc = vec2<f32>(
        (pixel.x / frame.viewport.x) * 2.0 - 1.0,
        1.0 - (pixel.y / frame.viewport.y) * 2.0,
    );

    var output: VertexOutput;
    output.position = vec4<f32>(ndc, 0.0, 1.0);
    output.color = item.color;
    output.local = local;
    output.size = item.rect.zw;
    output.radii = item.radii;
    return output;
}

fn selected_radius(local: vec2<f32>, size: vec2<f32>, radii: vec4<f32>) -> f32 {
    let left = local.x < size.x * 0.5;
    let top = local.y < size.y * 0.5;

    var radius: f32;
    if top {
        radius = select(radii.y, radii.x, left);
    } else {
        radius = select(radii.z, radii.w, left);
    }

    return clamp(radius, 0.0, min(size.x, size.y) * 0.5);
}

fn rounded_rect_distance(local: vec2<f32>, size: vec2<f32>, radii: vec4<f32>) -> f32 {
    let half_size = size * 0.5;
    let centered = local - half_size;
    let radius = selected_radius(local, size, radii);
    let q = abs(centered) - (half_size - vec2<f32>(radius));
    return min(max(q.x, q.y), 0.0) + length(max(q, vec2<f32>(0.0))) - radius;
}

@fragment
fn fs_main(input: VertexOutput) -> @location(0) vec4<f32> {
    let distance = rounded_rect_distance(input.local, input.size, input.radii);
    let antialias = max(fwidth(distance), 0.75);
    let coverage = 1.0 - smoothstep(-antialias, antialias, distance);
    return vec4<f32>(input.color.rgb, input.color.a * coverage);
}
