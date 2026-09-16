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
    let unit = corners[vertex_index];
    let local = unit * item.rect.zw;
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

fn rounded_corner_distance(
    local: vec2<f32>,
    size: vec2<f32>,
    radii: vec4<f32>,
) -> f32 {
    let max_radius = max(0.0, min(size.x, size.y) * 0.5);
    let top_left = min(max(radii.x, 0.0), max_radius);
    let top_right = min(max(radii.y, 0.0), max_radius);
    let bottom_right = min(max(radii.z, 0.0), max_radius);
    let bottom_left = min(max(radii.w, 0.0), max_radius);

    if local.x < top_left && local.y < top_left {
        return distance(local, vec2<f32>(top_left, top_left)) - top_left;
    }
    if local.x > size.x - top_right && local.y < top_right {
        return distance(local, vec2<f32>(size.x - top_right, top_right)) - top_right;
    }
    if local.x > size.x - bottom_right && local.y > size.y - bottom_right {
        return distance(
            local,
            vec2<f32>(size.x - bottom_right, size.y - bottom_right),
        ) - bottom_right;
    }
    if local.x < bottom_left && local.y > size.y - bottom_left {
        return distance(local, vec2<f32>(bottom_left, size.y - bottom_left)) - bottom_left;
    }
    return -1.0;
}

@fragment
fn fs_main(input: VertexOutput) -> @location(0) vec4<f32> {
    let edge_distance = rounded_corner_distance(input.local, input.size, input.radii);
    let antialias = max(fwidth(edge_distance), 0.75);
    let coverage = 1.0 - smoothstep(-antialias, antialias, edge_distance);
    return vec4<f32>(input.color.rgb, input.color.a * coverage);
}
