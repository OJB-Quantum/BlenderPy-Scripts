"""
Electrical-Arc Demo.

Generates a thick, GPU-ready electrical arc animation.
Compatible with Blender 2.93 up to 5.0+.

Authored by Onri Jay Benally (2025)

Open Access (CC-BY-4.0)
"""

import bpy
import math
import random
from mathutils import Vector, Matrix


# USER SETTINGS ----------------------------------------------------
# ------------------------------------------------------------------
ARC_THICKNESS = 0.04    # radius of the skin - increase to make the arc fatter
ARC_SEGMENTS = 90       # how many points the poly-line contains
ANIM_FRAMES = 300      # length of the animation
EMISSION_COL = (0.5, 0.8, 1.0, 1.0)   # light-blue RGBA
EMISSION_STRENGTH = 200.0
LIGHT_ENERGY = 1000.0


# Helper
def _clear_old_handler():
    """Remove any existing frame_change_pre handlers."""
    for h in bpy.app.handlers.frame_change_pre:
        if getattr(h, "__name__", "") == "arc_frame_handler":
            bpy.app.handlers.frame_change_pre.remove(h)
            break


# Create the zig-zag mesh that will become the arc
def create_zigzag_arc_mesh():
    """Return a Mesh datablock containing a simple poly-line."""
    mesh = bpy.data.meshes.new("ArcMesh")
    verts = []
    edges = []

    for i in range(ARC_SEGMENTS + 1):
        x = i * 2.0 - 5.0
        y = math.sin(i * 0.5) * 2.0
        z = random.uniform(-0.2, 0.2)

        verts.append((x, y, z))

        if i > 0:
            edges.append((i - 1, i))

    mesh.from_pydata(verts, edges, [])
    mesh.update()
    return mesh


# Material – pure emission node (no hidden sockets)
def create_arc_material():
    """Create and configure the ArcMaterial."""
    mat = bpy.data.materials.new(name="ArcMaterial")
    mat.use_nodes = True

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    # Emission node -------------------------------------------------
    emis = nodes.new(type='ShaderNodeEmission')
    emis.name = "ArcEmission"
    emis.location = (-200, 0)
    emis.inputs["Color"].default_value = EMISSION_COL
    emis.inputs["Strength"].default_value = EMISSION_STRENGTH

    # Material Output -------------------------------------------------
    out = nodes.new(type='ShaderNodeOutputMaterial')
    out.location = (0, 0)
    links.new(emis.outputs["Emission"], out.inputs["Surface"])

    return mat


# Light that follows the start of the arc
def add_arc_light():
    """Add a light object to follow the arc."""
    light_data = bpy.data.lights.new(name="ArcLight", type='POINT')
    light_data.color = EMISSION_COL[:3]
    light_data.energy = LIGHT_ENERGY
    light_data.shadow_soft_size = 0.5
    light_data.cycles.use_multiple_importance_sampling = True

    light_obj = bpy.data.objects.new("ArcLight", object_data=light_data)
    light_obj.location = (0, 0, 0)  # will be set each frame by the handler
    bpy.context.collection.objects.link(light_obj)

    return light_obj


# Frame-change handler – wiggles vertices and animates emission & light
def arc_frame_handler(scene):
    """Runs on every frame change."""
    frame = scene.frame_current
    arc_obj = scene.objects.get("ElectricalArc")

    if not arc_obj:
        return

    mesh = arc_obj.data

    # Keep a static copy of the original coordinates (used for Y/Z wiggle)
    base_coords = arc_obj.get("base_coords")
    if not base_coords:
        return  # should never happen, but guards against corrupt files

    # Wiggle every 2 frames (adds random Y and Z offsets)
    if frame % 2 == 0:
        for i, v in enumerate(mesh.vertices):
            bx, by, bz = base_coords[i]  # original positions
            v.co.x = bx
            v.co.y = by + random.uniform(-4.0, 4.0)  # Y-wiggle
            v.co.z = bz + random.uniform(-3.0, 3.0)  # Z-wiggle
        mesh.update()

    # Flicker emission strength every 3 frames
    if frame % 3 == 0:
        mat = bpy.data.materials.get("ArcMaterial")
        if mat:
            emis_node = mat.node_tree.nodes.get("ArcEmission")
            if emis_node:
                new_strength = EMISSION_STRENGTH + random.uniform(-50.0, 100.0)
                emis_node.inputs["Strength"].default_value = new_strength

    # Light follows the first vertex (world space)
    light_obj = scene.objects.get("ArcLight")
    if light_obj:
        tip_world = arc_obj.matrix_world @ mesh.vertices[0].co
        light_obj.location = tip_world


# Ensure there's a camera so the result is visible immediately
def ensure_camera():
    """Create and link a default camera if one does not exist."""
    if not any(obj.type == 'CAMERA' for obj in bpy.context.scene.objects):
        cam_data = bpy.data.cameras.new(name="ArcCam")
        cam_obj = bpy.data.objects.new("ArcCam", cam_data)
        cam_obj.location = (0, -12, 4)
        cam_obj.rotation_euler = (
            math.radians(75), 0, 0
        )
        bpy.context.collection.objects.link(cam_obj)
        bpy.context.scene.camera = cam_obj


# Main – assemble everything
def create_electrical_arc():
    """Create the electrical arc scene."""
    # Clean previous run -------------------------------------------------
    _clear_old_handler()
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'

    # GPU settings ------------------------------------------------------
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'CUDA'  # change to OPTIX / METAL if needed
    scene.cycles.device = 'GPU'

    # Geometry -----------------------------------------------------------
    arc_mesh = create_zigzag_arc_mesh()
    arc_obj = bpy.data.objects.new("ElectricalArc", arc_mesh)
    bpy.context.collection.objects.link(arc_obj)

    arc_obj["base_coords"] = [
        (v.co.x, v.co.y, v.co.z) for v in arc_obj.data.vertices
    ]

    # Thickening with Skin modifier ------------------------------------
    skin_mod = arc_obj.modifiers.new(name="Skin", type='SKIN')
    skin_mod.use_smooth_shade = True

    sub_mod = arc_obj.modifiers.new(name="Subdivision", type='SUBSURF')
    sub_mod.levels = 2
    sub_mod.render_levels = 2

    if arc_obj.data.skin_vertices:
        for sv in arc_obj.data.skin_vertices[0].data:
            sv.radius = (ARC_THICKNESS, ARC_THICKNESS)

    # Material -----------------------------------------------------------
    mat = create_arc_material()
    arc_obj.data.materials.append(mat)

    # Light --------------------------------------------------------------
    add_arc_light()  # its position will be set each frame by the handler

    # Animation timeline -----------------------------------------------
    scene.frame_start = 1
    scene.frame_end = ANIM_FRAMES

    # Render quality ------------------------------------------------------
    scene.cycles.samples = 64
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.use_denoising = True
    scene.cycles.denoiser = 'OPTIX'

    # Register the per-frame handler ------------------------------------
    if arc_frame_handler not in bpy.app.handlers.frame_change_pre:
        bpy.app.handlers.frame_change_pre.append(arc_frame_handler)

    # Camera ------------------------------------------------------------
    ensure_camera()


# Run the demo
if __name__ == "__main__":
    create_electrical_arc()
