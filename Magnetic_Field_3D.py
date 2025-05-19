'''
To generate some magnetic field lines for a single bar magnet, copy and paste the script I wrote below into your Blender Python scripting environment, found under the scripting tab in Blender. Then, run the script.

This work is open access and open source.
Authored by Onri Jay Benally (2025).
'''

import bpy
import numpy as np

# --- RENDER ENGINE SETTINGS ---
bpy.context.scene.render.engine = 'CYCLES'
prefs = bpy.context.preferences
cprefs = prefs.addons['cycles'].preferences
# Try to set GPU device if available
cprefs.compute_device_type = 'CUDA' if 'CUDA' in cprefs.get_device_types(bpy.context) else 'OPTIX' if 'OPTIX' in cprefs.get_device_types(bpy.context) else 'NONE'
bpy.context.scene.cycles.device = 'GPU'
for device in cprefs.devices:
    device.use = True

# --- PARAMETERS ---
num_seeds_theta = 8
num_seeds_phi = 12
steps_per_line = 100  # so each curve has up to 100 points
step_size = 0.18
magnet_length = 1.0
magnet_height = 1.0
magnet_moment = np.array([0, 0, 2.0])

# --- REMOVE OLD OBJECTS ---
for obj in bpy.context.scene.objects:
    if obj.name.startswith("FieldLine") or obj.name.startswith("BarMagnet"):
        bpy.data.objects.remove(obj, do_unlink=True)

# --- ADD BAR MAGNET ---
bpy.ops.mesh.primitive_cube_add(size=1)
magnet = bpy.context.object
magnet.name = "BarMagnet"
magnet.scale = (magnet_length/2, 0.5, magnet_height/2)
magnet.location = (0, 0, 0)
mat = bpy.data.materials.new("MagnetMaterial")
mat.diffuse_color = (0.3, 0.3, 0.7, 1.0)
magnet.data.materials.append(mat)

# --- FIELD FUNCTION ---
def B_field(pos, m=magnet_moment):
    r = np.array(pos)
    norm = np.linalg.norm(r)
    if norm < 0.1:
        norm = 0.1
    rhat = r / norm
    dot = np.dot(m, rhat)
    B = 3 * rhat * dot - m
    B = B / norm**3
    return B

# --- CREATE EMISSION MATERIAL ---
mat_curve = bpy.data.materials.get("CurveFieldEmission")
if not mat_curve:
    mat_curve = bpy.data.materials.new("CurveFieldEmission")
    mat_curve.use_nodes = True
    nodes = mat_curve.node_tree.nodes
    nodes.clear()
    # Add emission node
    emission_node = nodes.new(type='ShaderNodeEmission')
    emission_node.inputs['Color'].default_value = (0.0, 0.3, 1.0, 1.0)  # Bright blue
    emission_node.inputs['Strength'].default_value = 70.0
    output_node = nodes.new(type='ShaderNodeOutputMaterial')
    mat_curve.node_tree.links.new(emission_node.outputs[0], output_node.inputs[0])

# --- FIELD LINE CURVES ---
seed_radius = magnet_length * 0.4
seed_z = magnet_height/2 + 0.06
thetas = np.linspace(0.08, np.pi-0.08, num_seeds_theta)
phis = np.linspace(0, 2*np.pi, num_seeds_phi, endpoint=False)

fieldline_count = 0
for theta in thetas:
    for phi in phis:
        x0 = seed_radius * np.sin(theta) * np.cos(phi)
        y0 = seed_radius * np.sin(theta) * np.sin(phi)
        z0 = seed_z * np.cos(theta) + magnet_height/2 + 0.06
        seed = np.array([x0, y0, z0])
        pts = [seed.copy()]
        pos = seed.copy()
        for _ in range(steps_per_line):
            B = B_field(pos)
            dpos = B / np.linalg.norm(B) * step_size
            pos = pos + dpos
            pts.append(pos.copy())
            if np.linalg.norm(pos) > 7:
                break
        if len(pts) > 100:
            pts = pts[:100]
        # Create Blender curve
        curve_data = bpy.data.curves.new(f"FieldLineCurve{fieldline_count}", type='CURVE')
        curve_data.dimensions = '3D'
        curve_data.bevel_depth = 0.01  # 0.01 meters
        polyline = curve_data.splines.new('POLY')
        polyline.points.add(len(pts)-1)
        for k, co in enumerate(pts):
            polyline.points[k].co = (co[0], co[1], co[2], 1)
        curve_obj = bpy.data.objects.new(f"FieldLine_{fieldline_count}", curve_data)
        bpy.context.collection.objects.link(curve_obj)
        # Assign emission material
        curve_obj.data.materials.append(mat_curve)
        # --- SMOOTH THE CURVE CONTROL POINTS ---
        for spline in curve_obj.data.splines:
            for p in spline.points:
                p.select = True
        bpy.context.view_layer.objects.active = curve_obj
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.curve.select_all(action='SELECT')
        bpy.ops.curve.smooth()
        bpy.ops.object.mode_set(mode='OBJECT')
        # --- SUBDIVISION SURFACE MODIFIER (3 levels) ---
        mod = curve_obj.modifiers.new(name="Subdivision", type='SUBSURF')
        mod.levels = 3
        mod.render_levels = 3
        fieldline_count += 1

print("3D field lines generated: bevel=0.01, emission=blue 70, Cycles GPU, 3x subdivision, smoothed.")
