"""
Electrical-Arc Demo.

Generates a thick, GPU-ready electrical arc animation.
Compatible with Blender 2.93 up to 5.0+.

Authored by Onri Jay Benally (2025)

Open Access (CC-BY-4.0)
"""

import math
import random

import bpy
from mathutils import Vector, Matrix


# -----------------------------------------------------------------------------
# User Settings
# -----------------------------------------------------------------------------
ARC_THICKNESS = 0.04
ARC_SEGMENTS = 90
ANIM_FRAMES = 300
EMISSION_COL = (0.5, 0.8, 1.0, 1.0)
EMISSION_STRENGTH = 200.0
LIGHT_ENERGY = 1000.0


def _clear_old_handler():
    """Remove the specific frame handler if it exists to prevent duplication."""
    # iterate over a copy of the list to allow modification during iteration
    for handler in bpy.app.handlers.frame_change_pre[:]:
        if getattr(handler, "__name__", "") == "arc_frame_handler":
            bpy.app.handlers.frame_change_pre.remove(handler)


def create_zigzag_arc_mesh():
    """
    Create and return a Mesh datablock containing a simple poly-line.

    Returns:
        bpy.types.Mesh: The generated mesh data.
    """
    mesh = bpy.data.meshes.new("ArcMesh")
    verts = []
    edges = []

    for i in range(ARC_SEGMENTS + 1):
        # Spread along X
        x_pos = i * 2.0 - 5.0
        # Sine-wave shape
        y_pos = math.sin(i * 0.5) * 2.0
        # Small initial Z-noise
        z_pos = random.uniform(-0.2, 0.2)
        verts.append((x_pos, y_pos, z_pos))

        if i > 0:
            edges.append((i - 1, i))

    mesh.from_pydata(verts, edges, [])
    mesh.update()
    return mesh


def create_arc_material():
    """
    Create a pure emission node material.

    Returns:
        bpy.types.Material: The created material.
    """
    mat = bpy.data.materials.new(name="ArcMaterial")
    mat.use_nodes = True

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    # Emission node
    emis = nodes.new(type='ShaderNodeEmission')
    emis.name = "ArcEmission"
    emis.location = (-200, 0)
    emis.inputs["Color"].default_value = EMISSION_COL
    emis.inputs["Strength"].default_value = EMISSION_STRENGTH

    # Material Output
    out = nodes.new(type='ShaderNodeOutputMaterial')
    out.location = (0, 0)
    links.new(emis.outputs["Emission"], out.inputs["Surface"])

    return mat


def add_arc_light():
    """
    Create a point light that follows the start of the arc.

    Returns:
        bpy.types.Object: The light object.
    """
    light_data = bpy.data.lights.new(name="ArcLight", type='POINT')
    light_data.color = EMISSION_COL[:3]
    light_data.energy = LIGHT_ENERGY
    light_data.shadow_soft_size = 0.5
    light_data.cycles.use_multiple_importance_sampling = True

    light_obj = bpy.data.objects.new(name="ArcLight", object_data=light_data)
    # Location will be set each frame by the handler
    light_obj.location = (0, 0, 0)
    bpy.context.collection.objects.link(light_obj)
    return light_obj


def arc_frame_handler(scene):
    """
    Update geometry and lighting on every frame change.

    This function wiggles vertices (Y & Z axes), animates emission strength,
    and updates the light position.

    Args:
        scene (bpy.types.Scene): The current scene context.
    """
    frame = scene.frame_current
    arc_obj = scene.objects.get("ElectricalArc")
    if not arc_obj:
        return

    mesh = arc_obj.data

    # Retrieve static copy of original coordinates
    base_coords = arc_obj.get("base_coords")
    if not base_coords:
        return

    # Wiggle every 2 frames (adds random Y and Z offsets)
    if frame % 2 == 0:
        for i, vertex in enumerate(mesh.vertices):
            base_x, base_y, base_z = base_coords[i]
            # X stays the same (the arc still runs left-to-right)
            vertex.co.x = base_x
            # Small random jitter
            vertex.co.y = base_y + random.uniform(-4.0, 4.0)
            vertex.co.z = base_z + random.uniform(-3.0, 3.0)
        mesh.update()

    # Emission strength flicker (every 3 frames)
    if frame % 3 == 0:
        mat = bpy.data.materials.get("ArcMaterial")
        if mat:
            emis_node = mat.node_tree.nodes.get("ArcEmission")
            if emis_node:
                variation = random.uniform(-50.0, 100.0)
                new_strength = EMISSION_STRENGTH + variation
                emis_node.inputs["Strength"].default_value = new_strength

    # Light follows the first vertex (in world space)
    light_obj = scene.objects.get("ArcLight")
    if light_obj:
        tip_world = arc_obj.matrix_world @ mesh.vertices[0].co
        light_obj.location = tip_world


def ensure_camera():
    """Ensure a camera exists in the scene and position it for the demo."""
    if not any(obj.type == 'CAMERA' for obj in bpy.context.scene.objects):
        cam_data = bpy.data.cameras.new(name="ArcCam")
        cam_obj = bpy.data.objects.new("ArcCam", cam_data)
        cam_obj.location = (0, -12, 4)
        cam_obj.rotation_euler = (math.radians(75), 0, 0)
        bpy.context.collection.objects.link(cam_obj)
        bpy.context.scene.camera = cam_obj


def create_electrical_arc():
    """Assemble the scene, materials, objects, and handlers."""
    # Clean previous run
    _clear_old_handler()
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'

    # GPU settings
    prefs = bpy.context.preferences.addons['cycles'].preferences
    # Change to 'OPTIX' or 'METAL' if needed
    prefs.compute_device_type = 'CUDA'
    scene.cycles.device = 'GPU'

    # Geometry
    arc_mesh = create_zigzag_arc_mesh()
    arc_obj = bpy.data.objects.new("ElectricalArc", arc_mesh)
    bpy.context.collection.objects.link(arc_obj)

    # Store the original vertex positions (used for Y/Z wiggle)
    # Store as a plain Python list of tuples; this survives file saves.
    arc_obj["base_coords"] = [
        (v.co.x, v.co.y, v.co.z) for v in arc_obj.data.vertices
    ]

    # Skin Modifier
    skin_mod = arc_obj.modifiers.new(name="Skin", type='SKIN')
    skin_mod.use_smooth_shade = True

    # Subdivision Modifier
    sub_mod = arc_obj.modifiers.new(name="Subdivision", type='SUBSURF')
    sub_mod.levels = 2
    sub_mod.render_levels = 2

    # Uniform radius for every skin vertex
    if arc_obj.data.skin_vertices:
        for skin_vert in arc_obj.data.skin_vertices[0].data:
            skin_vert.radius = (ARC_THICKNESS, ARC_THICKNESS)

    # Material
    mat = create_arc_material()
    arc_obj.data.materials.append(mat)

    # Light
    add_arc_light()

    # Animation timeline
    scene.frame_start = 1
    scene.frame_end = ANIM_FRAMES

    # Render quality
    scene.cycles.samples = 64
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.use_denoising = True
    scene.cycles.denoiser = 'OPTIX'

    # Register the per-frame handler
    if arc_frame_handler not in bpy.app.handlers.frame_change_pre:
        bpy.app.handlers.frame_change_pre.append(arc_frame_handler)

    # Camera
    ensure_camera()


if __name__ == "__main__":
    create_electrical_arc()
