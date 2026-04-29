"""
Authored by Onri Jay Benally (2025)
Open Access (CC-BY-4.0)

Procedural 3D scenario generator:
Solar array -> ground power box -> Tesla Powerwall bank -> tool shed
containing an array of NVIDIA RTX PRO 6000 Blackwell GPU proxies.

Render:
- Cycles on CPU
- 3840 x 2160 (4K UHD)
- ~895 samples
- Orthographic isometric-style camera

Notes:
- This script intentionally uses simplified proxy geometry.
- Tested for Blender 3.6+ / 4.x style APIs with defensive checks.

Optional linting:
- pylint can be used, but Blender's bpy module is dynamic; expect
  false positives unless you configure stubs.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple

import bpy
from mathutils import Vector


# -----------------------------
# Control knobs (edit these)
# -----------------------------

@dataclass(frozen=True)
class SceneConfig:
    # Output controls
    output_path: str = "//powerwall_solar_gpu_shed_isometric_4k.png"
    save_blend_path: Optional[str] = "//powerwall_solar_gpu_shed_scene.blend"
    do_render: bool = True
    do_save_blend: bool = False

    # Render controls (requested)
    render_engine: str = "CYCLES"
    cycles_device: str = "CPU"
    samples: int = 895
    resolution_x: int = 3840
    resolution_y: int = 2160

    # Scene layout controls
    powerwall_count: int = 11
    gpu_count: int = 16
    racks_count: int = 2  # 2 racks => 2 x 8 GPU proxies by default

    # Solar layout
    solar_rows: int = 3
    solar_cols: int = 5
    solar_panel_w: float = 1.00
    solar_panel_h: float = 1.70
    solar_panel_thickness: float = 0.05
    solar_panel_gap_x: float = 0.15
    solar_panel_gap_y: float = 0.20
    solar_tilt_deg: float = 25.0

    # Powerwall proxy dimensions (meters, intentionally approximate)
    powerwall_w: float = 0.65
    powerwall_d: float = 0.18
    powerwall_h: float = 1.15
    powerwall_gap: float = 0.25

    # Shed dimensions
    shed_w: float = 4.80
    shed_d: float = 3.40
    shed_h: float = 2.70
    shed_wall_thickness: float = 0.10

    # Rack/GPU proxy sizing
    rack_w: float = 0.70
    rack_d: float = 1.00
    rack_h: float = 2.20
    gpu_w: float = 0.35
    gpu_d: float = 0.05
    gpu_h: float = 0.12  # "height" when mounted in rack
    gpu_shelf_levels: int = 4
    gpu_per_shelf: int = 2

    # Cable visuals
    cable_radius: float = 0.03

    # Camera
    camera_distance: float = 22.0  # only affects clipping; ortho scale controls framing
    camera_dir: Tuple[float, float, float] = (1.0, -1.0, 1.0)  # isometric-like
    camera_margin: float = 1.25  # expands ortho_scale framing


CFG = SceneConfig()


# -----------------------------
# Utilities
# -----------------------------

def _safe_orphans_purge() -> None:
    """Attempt to purge orphan data blocks; ignore if context disallows."""
    try:
        for _ in range(3):
            bpy.ops.outliner.orphans_purge(
                do_local_ids=True,
                do_linked_ids=True,
                do_recursive=True,
            )
    except Exception:
        # In some contexts (especially headless), this can fail harmlessly.
        pass


def clear_scene() -> None:
    """Delete all objects and reset to a clean-ish slate."""
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    _safe_orphans_purge()

    # Reset world nodes if present.
    if bpy.data.worlds:
        world = bpy.data.worlds[0]
        world.use_nodes = True
        nt = world.node_tree
        for node in list(nt.nodes):
            nt.nodes.remove(node)


def set_units_metric(scene: bpy.types.Scene) -> None:
    """Use metric meters for predictable sizing."""
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0


def make_material_principled(
    name: str,
    base_color: Tuple[float, float, float, float],
    metallic: float = 0.0,
    roughness: float = 0.5,
    emission_strength: float = 0.0,
    emission_color: Optional[Tuple[float, float, float, float]] = None,
) -> bpy.types.Material:
    """Create (or reuse) a Principled BSDF material with optional emission."""
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nt = mat.node_tree
    nodes = nt.nodes
    links = nt.links

    for node in list(nodes):
        nodes.remove(node)

    out = nodes.new(type="ShaderNodeOutputMaterial")
    out.location = (300, 0)

    principled = nodes.new(type="ShaderNodeBsdfPrincipled")
    principled.location = (0, 0)
    principled.inputs["Base Color"].default_value = base_color
    principled.inputs["Metallic"].default_value = metallic
    principled.inputs["Roughness"].default_value = roughness

    shader_socket = principled.outputs["BSDF"]

    if emission_strength > 0.0:
        emit = nodes.new(type="ShaderNodeEmission")
        emit.location = (0, -220)
        emit.inputs["Strength"].default_value = emission_strength
        emit.inputs["Color"].default_value = (
            emission_color if emission_color is not None else base_color
        )

        add = nodes.new(type="ShaderNodeAddShader")
        add.location = (150, -80)
        links.new(principled.outputs["BSDF"], add.inputs[0])
        links.new(emit.outputs["Emission"], add.inputs[1])
        shader_socket = add.outputs["Shader"]

    links.new(shader_socket, out.inputs["Surface"])
    return mat


def assign_material(obj: bpy.types.Object, mat: bpy.types.Material) -> None:
    """Assign a material to an object, replacing slot 0."""
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)


def add_cube(
    name: str,
    size_xyz: Tuple[float, float, float],
    location: Tuple[float, float, float],
    rotation_euler: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    bevel: bool = False,
    bevel_width: float = 0.02,
) -> bpy.types.Object:
    """Add a cube scaled to exact size in meters."""
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location, rotation=rotation_euler)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (size_xyz[0] / 2.0, size_xyz[1] / 2.0, size_xyz[2] / 2.0)

    if bevel:
        mod = obj.modifiers.new(name=f"{name}_bevel", type="BEVEL")
        mod.width = bevel_width
        mod.segments = 3
        mod.profile = 0.7

    return obj


def add_plane(
    name: str,
    size_xy: Tuple[float, float],
    location: Tuple[float, float, float],
    rotation_euler: Tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> bpy.types.Object:
    """Add a plane with given X/Y size in meters."""
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=location, rotation=rotation_euler)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (size_xy[0], size_xy[1], 1.0)
    return obj


def add_cylinder(
    name: str,
    radius: float,
    depth: float,
    location: Tuple[float, float, float],
    rotation_euler: Tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cylinder_add(
        radius=radius,
        depth=depth,
        location=location,
        rotation=rotation_euler,
    )
    obj = bpy.context.active_object
    obj.name = name
    return obj


def add_cable_curve(
    name: str,
    points: Sequence[Tuple[float, float, float]],
    radius: float,
    material: bpy.types.Material,
) -> bpy.types.Object:
    """Create a beveled curve polyline as a 'cable'."""
    curve_data = bpy.data.curves.new(name=f"{name}_curve", type="CURVE")
    curve_data.dimensions = "3D"
    curve_data.resolution_u = 12

    poly = curve_data.splines.new(type="POLY")
    poly.points.add(len(points) - 1)
    for i, (x, y, z) in enumerate(points):
        poly.points[i].co = (x, y, z, 1.0)

    curve_data.bevel_depth = radius
    curve_data.bevel_resolution = 6

    obj = bpy.data.objects.new(name, curve_data)
    bpy.context.collection.objects.link(obj)

    # Material for curves lives on curve data.
    if curve_data.materials:
        curve_data.materials[0] = material
    else:
        curve_data.materials.append(material)

    return obj


def compute_scene_bounds(objects: Iterable[bpy.types.Object]) -> Tuple[Vector, Vector]:
    """Compute world-space AABB bounds for the given objects."""
    min_v = Vector((math.inf, math.inf, math.inf))
    max_v = Vector((-math.inf, -math.inf, -math.inf))

    for obj in objects:
        if obj.type in {"CAMERA", "LIGHT"}:
            continue
        if obj.hide_render:
            continue
        # Some objects (curves) still have bound_box.
        for corner in obj.bound_box:
            world_corner = obj.matrix_world @ Vector(corner)
            min_v.x = min(min_v.x, world_corner.x)
            min_v.y = min(min_v.y, world_corner.y)
            min_v.z = min(min_v.z, world_corner.z)
            max_v.x = max(max_v.x, world_corner.x)
            max_v.y = max(max_v.y, world_corner.y)
            max_v.z = max(max_v.z, world_corner.z)

    if not math.isfinite(min_v.x):
        # Fallback if nothing is present.
        min_v = Vector((-1.0, -1.0, -1.0))
        max_v = Vector((1.0, 1.0, 1.0))
    return min_v, max_v


# -----------------------------
# Scene construction
# -----------------------------

def build_ground(material_ground: bpy.types.Material) -> bpy.types.Object:
    ground = add_plane(
        name="Ground",
        size_xy=(50.0, 50.0),
        location=(0.0, 0.0, 0.0),
        rotation_euler=(0.0, 0.0, 0.0),
    )
    assign_material(ground, material_ground)
    return ground


def build_solar_array(
    origin: Tuple[float, float, float],
    material_panel: bpy.types.Material,
    material_frame: bpy.types.Material,
    material_support: bpy.types.Material,
) -> bpy.types.Object:
    """Build a simple tilted solar array and return a parent empty."""
    parent = bpy.data.objects.new("SolarArray", None)
    parent.empty_display_type = "PLAIN_AXES"
    parent.location = origin
    bpy.context.collection.objects.link(parent)

    tilt = math.radians(CFG.solar_tilt_deg)

    # Base frame rails
    rail_len = (
        CFG.solar_cols * CFG.solar_panel_w
        + (CFG.solar_cols - 1) * CFG.solar_panel_gap_x
        + 0.3
    )
    rail_w = 0.06
    rail_h = 0.06

    rail_y0 = -(
        (CFG.solar_rows - 1) * (CFG.solar_panel_h + CFG.solar_panel_gap_y)
    ) * 0.5
    rail_y1 = -rail_y0

    rail_z = 0.45

    rail0 = add_cube(
        "SolarRail_0",
        size_xyz=(rail_len, rail_w, rail_h),
        location=(origin[0], origin[1] + rail_y0, origin[2] + rail_z),
        bevel=True,
        bevel_width=0.01,
    )
    assign_material(rail0, material_support)
    rail0.parent = parent

    rail1 = add_cube(
        "SolarRail_1",
        size_xyz=(rail_len, rail_w, rail_h),
        location=(origin[0], origin[1] + rail_y1, origin[2] + rail_z),
        bevel=True,
        bevel_width=0.01,
    )
    assign_material(rail1, material_support)
    rail1.parent = parent

    # Panels
    start_x = -(
        (CFG.solar_cols - 1) * (CFG.solar_panel_w + CFG.solar_panel_gap_x)
    ) * 0.5
    start_y = -(
        (CFG.solar_rows - 1) * (CFG.solar_panel_h + CFG.solar_panel_gap_y)
    ) * 0.5

    panel_z_base = origin[2] + 0.55

    for r in range(CFG.solar_rows):
        for c in range(CFG.solar_cols):
            x = origin[0] + start_x + c * (CFG.solar_panel_w + CFG.solar_panel_gap_x)
            y = origin[1] + start_y + r * (CFG.solar_panel_h + CFG.solar_panel_gap_y)

            # Panel frame (slightly larger)
            frame = add_cube(
                name=f"SolarFrame_r{r}_c{c}",
                size_xyz=(
                    CFG.solar_panel_w + 0.06,
                    CFG.solar_panel_h + 0.06,
                    CFG.solar_panel_thickness,
                ),
                location=(x, y, panel_z_base),
                rotation_euler=(tilt, 0.0, 0.0),
                bevel=True,
                bevel_width=0.005,
            )
            assign_material(frame, material_frame)
            frame.parent = parent

            panel = add_cube(
                name=f"SolarPanel_r{r}_c{c}",
                size_xyz=(
                    CFG.solar_panel_w,
                    CFG.solar_panel_h,
                    CFG.solar_panel_thickness * 0.55,
                ),
                location=(x, y, panel_z_base + 0.006),
                rotation_euler=(tilt, 0.0, 0.0),
                bevel=False,
            )
            assign_material(panel, material_panel)
            panel.parent = parent

    # Support posts (four)
    post_r = 0.05
    post_h = 0.85
    post_offsets = [
        (-rail_len * 0.45, rail_y0, 0.0),
        ( rail_len * 0.45, rail_y0, 0.0),
        (-rail_len * 0.45, rail_y1, 0.0),
        ( rail_len * 0.45, rail_y1, 0.0),
    ]
    for i, (dx, dy, dz) in enumerate(post_offsets):
        post = add_cylinder(
            name=f"SolarPost_{i}",
            radius=post_r,
            depth=post_h,
            location=(origin[0] + dx, origin[1] + dy, origin[2] + post_h / 2.0),
        )
        assign_material(post, material_support)
        post.parent = parent

    return parent


def build_power_box(
    location: Tuple[float, float, float],
    material_box: bpy.types.Material,
) -> bpy.types.Object:
    box = add_cube(
        name="PowerBox",
        size_xyz=(0.80, 0.50, 0.90),
        location=(location[0], location[1], location[2] + 0.45),
        bevel=True,
        bevel_width=0.02,
    )
    assign_material(box, material_box)
    return box


def build_powerwall_bank(
    start_location: Tuple[float, float, float],
    material_powerwall: bpy.types.Material,
    material_trim: bpy.types.Material,
) -> bpy.types.Object:
    """Create a line array of Powerwall-like enclosures; return parent empty."""
    parent = bpy.data.objects.new("PowerwallBank", None)
    parent.empty_display_type = "PLAIN_AXES"
    parent.location = start_location
    bpy.context.collection.objects.link(parent)

    for i in range(CFG.powerwall_count):
        x = start_location[0] + i * (CFG.powerwall_w + CFG.powerwall_gap)
        y = start_location[1]
        z = start_location[2]

        wall = add_cube(
            name=f"Powerwall_{i:02d}",
            size_xyz=(CFG.powerwall_w, CFG.powerwall_d, CFG.powerwall_h),
            location=(x, y, z + CFG.powerwall_h / 2.0),
            bevel=True,
            bevel_width=0.02,
        )
        assign_material(wall, material_powerwall)
        wall.parent = parent

        # A subtle front "trim" plate to suggest branding face
        trim = add_cube(
            name=f"PowerwallTrim_{i:02d}",
            size_xyz=(CFG.powerwall_w * 0.92, CFG.powerwall_d * 0.20, CFG.powerwall_h * 0.86),
            location=(x, y + CFG.powerwall_d * 0.41, z + CFG.powerwall_h / 2.0),
            bevel=True,
            bevel_width=0.01,
        )
        assign_material(trim, material_trim)
        trim.parent = parent

    # Concrete pad under Powerwalls
    pad_len = CFG.powerwall_count * CFG.powerwall_w + (CFG.powerwall_count - 1) * CFG.powerwall_gap + 0.6
    pad = add_cube(
        name="PowerwallPad",
        size_xyz=(pad_len, CFG.powerwall_d + 0.8, 0.10),
        location=(
            start_location[0] + (pad_len - 0.6) / 2.0 - 0.3,
            start_location[1],
            start_location[2] + 0.05,
        ),
        bevel=True,
        bevel_width=0.01,
    )
    assign_material(pad, material_trim)
    pad.parent = parent

    return parent


def build_tool_shed(
    location: Tuple[float, float, float],
    material_shed: bpy.types.Material,
    material_roof: bpy.types.Material,
    material_floor: bpy.types.Material,
) -> bpy.types.Object:
    """Build a simple shed with an open front so racks are visible."""
    parent = bpy.data.objects.new("ToolShed", None)
    parent.empty_display_type = "PLAIN_AXES"
    parent.location = location
    bpy.context.collection.objects.link(parent)

    # Floor slab
    floor = add_cube(
        name="ShedFloor",
        size_xyz=(CFG.shed_w, CFG.shed_d, 0.12),
        location=(location[0], location[1], location[2] + 0.06),
        bevel=True,
        bevel_width=0.01,
    )
    assign_material(floor, material_floor)
    floor.parent = parent

    wt = CFG.shed_wall_thickness
    half_w = CFG.shed_w / 2.0
    half_d = CFG.shed_d / 2.0
    wall_z = location[2] + 0.12 + CFG.shed_h / 2.0

    # Back wall
    back = add_cube(
        name="ShedWall_Back",
        size_xyz=(CFG.shed_w, wt, CFG.shed_h),
        location=(location[0], location[1] - half_d + wt / 2.0, wall_z),
        bevel=True,
        bevel_width=0.01,
    )
    assign_material(back, material_shed)
    back.parent = parent

    # Left wall
    left = add_cube(
        name="ShedWall_Left",
        size_xyz=(wt, CFG.shed_d, CFG.shed_h),
        location=(location[0] - half_w + wt / 2.0, location[1], wall_z),
        bevel=True,
        bevel_width=0.01,
    )
    assign_material(left, material_shed)
    left.parent = parent

    # Right wall
    right = add_cube(
        name="ShedWall_Right",
        size_xyz=(wt, CFG.shed_d, CFG.shed_h),
        location=(location[0] + half_w - wt / 2.0, location[1], wall_z),
        bevel=True,
        bevel_width=0.01,
    )
    assign_material(right, material_shed)
    right.parent = parent

    # Roof (slight pitch)
    roof = add_cube(
        name="ShedRoof",
        size_xyz=(CFG.shed_w + 0.15, CFG.shed_d + 0.15, 0.12),
        location=(location[0], location[1], location[2] + 0.12 + CFG.shed_h + 0.10),
        rotation_euler=(math.radians(6.0), 0.0, 0.0),
        bevel=True,
        bevel_width=0.01,
    )
    assign_material(roof, material_roof)
    roof.parent = parent

    return parent


def build_racks_and_gpus(
    shed_location: Tuple[float, float, float],
    material_rack: bpy.types.Material,
    material_gpu: bpy.types.Material,
    material_gpu_accent: bpy.types.Material,
) -> bpy.types.Object:
    """Place racks and GPU proxies inside the shed; return parent empty."""
    parent = bpy.data.objects.new("ComputeRacks", None)
    parent.empty_display_type = "PLAIN_AXES"
    parent.location = shed_location
    bpy.context.collection.objects.link(parent)

    # Place racks near the back wall, evenly spaced.
    racks = []
    racks_count = max(1, CFG.racks_count)
    x0 = shed_location[0] - (racks_count - 1) * (CFG.rack_w + 0.25) * 0.5
    y = shed_location[1] - (CFG.shed_d * 0.30)
    z = shed_location[2] + 0.12 + CFG.rack_h / 2.0

    for i in range(racks_count):
        rack = add_cube(
            name=f"Rack_{i:02d}",
            size_xyz=(CFG.rack_w, CFG.rack_d, CFG.rack_h),
            location=(x0 + i * (CFG.rack_w + 0.25), y, z),
            bevel=True,
            bevel_width=0.01,
        )
        assign_material(rack, material_rack)
        rack.parent = parent
        racks.append(rack)

    # Distribute GPUs across racks.
    gpu_total = max(1, CFG.gpu_count)
    base_per_rack = gpu_total // racks_count
    remainder = gpu_total % racks_count

    gpu_index = 0
    for r_i, rack in enumerate(racks):
        n_gpu = base_per_rack + (1 if r_i < remainder else 0)

        # Layout within rack: shelves x positions
        shelf_levels = max(1, CFG.gpu_shelf_levels)
        per_shelf = max(1, CFG.gpu_per_shelf)
        capacity = shelf_levels * per_shelf
        n_gpu = min(n_gpu, capacity)

        for j in range(n_gpu):
            shelf = j // per_shelf
            slot = j % per_shelf

            # Local coordinates relative to rack center.
            x_off = (-0.18 if slot == 0 else 0.18)
            y_off = (CFG.rack_d * 0.10)  # slightly forward inside rack
            z_low = shed_location[2] + 0.12 + 0.25
            z_step = (CFG.rack_h - 0.60) / max(1, shelf_levels - 1)
            z_pos = z_low + shelf * z_step

            gpu = add_cube(
                name=f"GPU_RTX_PRO_6000_Blackwell_{gpu_index:02d}",
                size_xyz=(CFG.gpu_w, CFG.gpu_d, CFG.gpu_h),
                location=(
                    rack.location.x + x_off,
                    rack.location.y + y_off,
                    z_pos,
                ),
                bevel=True,
                bevel_width=0.004,
            )
            assign_material(gpu, material_gpu)
            gpu.parent = parent

            # Small accent strip (suggests heatsink/shroud detail)
            accent = add_cube(
                name=f"GPU_Accent_{gpu_index:02d}",
                size_xyz=(CFG.gpu_w * 0.92, CFG.gpu_d * 0.15, CFG.gpu_h * 0.25),
                location=(
                    rack.location.x + x_off,
                    rack.location.y + y_off + CFG.gpu_d * 0.42,
                    z_pos,
                ),
                bevel=True,
                bevel_width=0.003,
            )
            assign_material(accent, material_gpu_accent)
            accent.parent = parent

            gpu_index += 1

    return parent


# -----------------------------
# Lighting and camera
# -----------------------------

def setup_world_sky(scene: bpy.types.Scene) -> None:
    """Create a simple procedural sky-like background."""
    world = scene.world
    world.use_nodes = True
    nt = world.node_tree
    nodes = nt.nodes
    links = nt.links

    bg = nodes.new(type="ShaderNodeBackground")
    bg.location = (0, 0)
    bg.inputs["Strength"].default_value = 1.0

    sky = nodes.new(type="ShaderNodeTexSky")
    sky.location = (-220, 0)
    # Some Blender versions have different sky parameters; keep defaults.

    out = nodes.new(type="ShaderNodeOutputWorld")
    out.location = (220, 0)

    links.new(sky.outputs["Color"], bg.inputs["Color"])
    links.new(bg.outputs["Background"], out.inputs["Surface"])


def add_lights() -> None:
    """Add a sun and a soft area light to keep the scene readable."""
    bpy.ops.object.light_add(type="SUN", location=(12.0, -10.0, 18.0))
    sun = bpy.context.active_object
    sun.name = "SunLight"
    sun.data.energy = 3.0
    sun.rotation_euler = (math.radians(55), 0.0, math.radians(35))

    bpy.ops.object.light_add(type="AREA", location=(-8.0, 8.0, 10.0))
    area = bpy.context.active_object
    area.name = "FillArea"
    area.data.energy = 600.0
    area.data.size = 6.0
    area.rotation_euler = (math.radians(65), 0.0, math.radians(-35))


def setup_isometric_camera(scene: bpy.types.Scene) -> bpy.types.Object:
    """Create an orthographic camera aimed at the scene bounds."""
    # Camera object
    bpy.ops.object.camera_add()
    cam = bpy.context.active_object
    cam.name = "IsoCamera"
    cam.data.type = "ORTHO"

    # Find bounds center
    objs = list(bpy.data.objects)
    min_v, max_v = compute_scene_bounds(objs)
    center = (min_v + max_v) * 0.5

    # Position camera along an isometric direction
    dir_v = Vector(CFG.camera_dir).normalized()
    cam.location = center + dir_v * CFG.camera_distance

    # Aim camera at center
    look_dir = center - cam.location
    cam.rotation_euler = look_dir.to_track_quat("-Z", "Y").to_euler()

    # Ortho scale: fit X/Y extents with a margin
    span = max(max_v.x - min_v.x, max_v.y - min_v.y)
    cam.data.ortho_scale = max(6.0, span * CFG.camera_margin)

    # Clip planes
    cam.data.clip_start = 0.1
    cam.data.clip_end = 500.0

    scene.camera = cam
    return cam


# -----------------------------
# Render configuration
# -----------------------------

def configure_render(scene: bpy.types.Scene) -> None:
    scene.render.engine = CFG.render_engine
    scene.render.resolution_x = CFG.resolution_x
    scene.render.resolution_y = CFG.resolution_y
    scene.render.resolution_percentage = 100

    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "16"
    scene.render.filepath = CFG.output_path

    # Cycles settings
    if hasattr(scene, "cycles"):
        scene.cycles.device = CFG.cycles_device
        scene.cycles.samples = CFG.samples

        # Conservative bounces for outdoor-ish scene; adjust as needed.
        scene.cycles.max_bounces = 8
        scene.cycles.diffuse_bounces = 3
        scene.cycles.glossy_bounces = 3
        scene.cycles.transparent_max_bounces = 8

    # Denoising (API differs across versions)
    view_layer = scene.view_layers[0]
    if hasattr(view_layer, "cycles"):
        view_layer.cycles.use_denoising = True
        if hasattr(view_layer.cycles, "denoiser"):
            view_layer.cycles.denoiser = "OPENIMAGEDENOISE"
    if hasattr(scene, "cycles") and hasattr(scene.cycles, "use_denoising"):
        scene.cycles.use_denoising = True
        if hasattr(scene.cycles, "denoiser"):
            scene.cycles.denoiser = "OPENIMAGEDENOISE"

    # Color management (Filmic is default in many installs; keep stable)
    scene.view_settings.exposure = 0.0


# -----------------------------
# Main
# -----------------------------

def main() -> None:
    scene = bpy.context.scene
    clear_scene()
    set_units_metric(scene)

    # Materials
    mat_ground = make_material_principled(
        "MAT_Ground",
        base_color=(0.20, 0.22, 0.23, 1.0),
        metallic=0.0,
        roughness=0.9,
    )
    mat_powerwall = make_material_principled(
        "MAT_Powerwall",
        base_color=(0.90, 0.90, 0.92, 1.0),
        metallic=0.0,
        roughness=0.35,
    )
    mat_trim = make_material_principled(
        "MAT_Trim",
        base_color=(0.55, 0.57, 0.60, 1.0),
        metallic=0.0,
        roughness=0.6,
    )
    mat_solar_panel = make_material_principled(
        "MAT_SolarPanel",
        base_color=(0.05, 0.08, 0.14, 1.0),
        metallic=0.0,
        roughness=0.25,
        emission_strength=0.15,
        emission_color=(0.06, 0.10, 0.16, 1.0),
    )
    mat_solar_frame = make_material_principled(
        "MAT_SolarFrame",
        base_color=(0.08, 0.08, 0.09, 1.0),
        metallic=0.7,
        roughness=0.35,
    )
    mat_support = make_material_principled(
        "MAT_Support",
        base_color=(0.12, 0.12, 0.13, 1.0),
        metallic=0.85,
        roughness=0.30,
    )
    mat_box = make_material_principled(
        "MAT_PowerBox",
        base_color=(0.25, 0.26, 0.28, 1.0),
        metallic=0.1,
        roughness=0.65,
    )
    mat_shed = make_material_principled(
        "MAT_Shed",
        base_color=(0.32, 0.30, 0.28, 1.0),
        metallic=0.0,
        roughness=0.85,
    )
    mat_roof = make_material_principled(
        "MAT_Roof",
        base_color=(0.12, 0.12, 0.13, 1.0),
        metallic=0.2,
        roughness=0.7,
    )
    mat_floor = make_material_principled(
        "MAT_ShedFloor",
        base_color=(0.18, 0.18, 0.19, 1.0),
        metallic=0.0,
        roughness=0.8,
    )
    mat_rack = make_material_principled(
        "MAT_Rack",
        base_color=(0.10, 0.10, 0.11, 1.0),
        metallic=0.7,
        roughness=0.4,
    )
    mat_gpu = make_material_principled(
        "MAT_GPU",
        base_color=(0.06, 0.06, 0.07, 1.0),
        metallic=0.2,
        roughness=0.3,
    )
    mat_gpu_accent = make_material_principled(
        "MAT_GPU_Accent",
        base_color=(0.12, 0.50, 0.20, 1.0),
        metallic=0.1,
        roughness=0.25,
        emission_strength=0.2,
        emission_color=(0.10, 0.65, 0.18, 1.0),
    )
    mat_cable = make_material_principled(
        "MAT_Cable",
        base_color=(0.02, 0.02, 0.02, 1.0),
        metallic=0.0,
        roughness=0.8,
    )

    # Build elements
    build_ground(mat_ground)

    solar_origin = (-10.0, 6.0, 0.0)
    solar = build_solar_array(
        origin=solar_origin,
        material_panel=mat_solar_panel,
        material_frame=mat_solar_frame,
        material_support=mat_support,
    )

    power_box_loc = (-4.0, 4.5, 0.0)
    power_box = build_power_box(power_box_loc, mat_box)

    powerwall_start = (-2.0, 0.0, 0.0)
    powerwalls = build_powerwall_bank(powerwall_start, mat_powerwall, mat_trim)

    shed_loc = (7.5, -1.5, 0.0)
    shed = build_tool_shed(
        location=shed_loc,
        material_shed=mat_shed,
        material_roof=mat_roof,
        material_floor=mat_floor,
    )
    build_racks_and_gpus(
        shed_location=shed_loc,
        material_rack=mat_rack,
        material_gpu=mat_gpu,
        material_gpu_accent=mat_gpu_accent,
    )

    # Cables: solar -> box -> powerwalls -> shed
    # Compute some anchor points
    solar_anchor = Vector(solar_origin) + Vector((0.0, 0.0, 0.6))
    box_anchor = Vector((power_box.location.x, power_box.location.y, 0.9))
    pw_anchor = Vector((powerwall_start[0], powerwall_start[1] + CFG.powerwall_d * 0.5, 0.9))
    shed_anchor = Vector((shed_loc[0] - CFG.shed_w * 0.5 + 0.2, shed_loc[1] + CFG.shed_d * 0.2, 1.2))

    add_cable_curve(
        "Cable_Solar_to_Box",
        points=[
            (solar_anchor.x, solar_anchor.y, solar_anchor.z),
            (solar_anchor.x + 2.0, solar_anchor.y - 1.0, solar_anchor.z),
            (box_anchor.x, box_anchor.y, box_anchor.z),
        ],
        radius=CFG.cable_radius,
        material=mat_cable,
    )

    add_cable_curve(
        "Cable_Box_to_Powerwalls",
        points=[
            (box_anchor.x, box_anchor.y, box_anchor.z),
            (box_anchor.x + 1.5, box_anchor.y - 1.5, 0.7),
            (pw_anchor.x, pw_anchor.y, pw_anchor.z),
        ],
        radius=CFG.cable_radius,
        material=mat_cable,
    )

    add_cable_curve(
        "Cable_Powerwalls_to_Shed",
        points=[
            (pw_anchor.x + CFG.powerwall_count * (CFG.powerwall_w + CFG.powerwall_gap) - 0.8,
             pw_anchor.y,
             pw_anchor.z),
            (pw_anchor.x + 6.0, pw_anchor.y - 1.0, 0.8),
            (shed_anchor.x, shed_anchor.y, shed_anchor.z),
        ],
        radius=CFG.cable_radius,
        material=mat_cable,
    )

    # World, lights, camera, render settings
    setup_world_sky(scene)
    add_lights()
    setup_isometric_camera(scene)

if __name__ == "__main__":
    main()
