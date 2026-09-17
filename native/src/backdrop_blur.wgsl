struct BackdropParams {
    viewport: vec2<f32>,
    origin: vec2<f32>,
    size: vec2<f32>,
    padding: vec2<f32>,
    radii: vec4<f32>,
};

@group(0) @binding(0)
var source_texture: texture_2d<f32>;

@group(0) @binding(1)
var source_sampler: sampler;

@group(0) @binding(2)
var<uniform> params: BackdropParams;

struct VertexOutput {
    @builtin(position) position: vec4<f32>,
    @location(0) uv: vec2<f32>,
};

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
    let pixel = input.uv * params.viewport;
    let local = pixel - params.origin;
    if local.x < 0.0 || local.y < 0.0 || local.x >= params.size.x || local.y >= params.size.y {
        discard;
    }

    let distance = rounded_rect_distance(local, params.size, params.radii);
    let antialias = max(fwidth(distance), 0.75);
    let coverage = 1.0 - smoothstep(-antialias, antialias, distance);
    if coverage <= 0.0 {
        discard;
    }

    let blurred = textureSample(source_texture, source_sampler, input.uv);
    return vec4<f32>(blurred.rgb, coverage);
}
