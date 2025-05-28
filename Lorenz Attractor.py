# Authored by Onri Jay Benally (2025), free and open sourced script

import bpy
import numpy as np

# --- LORENZ SYSTEM PARAMETERS ---
sigma = 10.0
rho   = 28.0
beta  = 8.0 / 3.0

dt        = 0.005      # time step
num_steps = 8000       # number of integration steps

# initial condition
x, y, z = 0.1, 0.0, 0.0

# integrate Lorenz equations
points = []
for i in range(num_steps):
    dx = sigma * (y - x)
    dy = x * (rho - z) - y
    dz = x * y - beta * z

    x += dx * dt
    y += dy * dt
    z += dz * dt

    points.append((x, y, z))

# --- CREATE CURVE DATA ---
curve_data = bpy.data.curves.new(name="LorenzCurve", type='CURVE')
curve_data.dimensions = '3D'
curve_data.resolution_u = 2  # controls interpolation resolution

# create one polyline spline and assign points
spline = curve_data.splines.new(type='POLY')
spline.points.add(len(points) - 1)
for idx, coord in enumerate(points):
    x, y, z = coord
    spline.points[idx].co = (x, y, z, 1)

# set bevel depth for thickness (in meters)
curve_data.bevel_depth = 0.012
curve_data.bevel_resolution = 4  # smooth circular cross-section

# --- CREATE OBJECT AND LINK TO SCENE ---
curve_obj = bpy.data.objects.new("LorenzAttractor", curve_data)
bpy.context.collection.objects.link(curve_obj)

# center the view on the curve
bpy.context.view_layer.objects.active = curve_obj
curve_obj.select_set(True)
# --- OPTIONAL: Center the view in a real 3D View area ---
for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        with bpy.context.temp_override(area=area, region=area.regions[-1]):
            bpy.ops.view3d.view_selected()
        break

# --- ADD SUBSURF MODIFIER ---
subsurf = curve_obj.modifiers.new(name="Subsurf", type='SUBSURF')
subsurf.levels = 2
subsurf.render_levels = 2
subsurf.subdivision_type = 'CATMULL_CLARK'


# --- CREATE BLUE EMISSION MATERIAL ---
mat = bpy.data.materials.new(name="BlueEmission")
mat.use_nodes = True
nodes = mat.node_tree.nodes
links = mat.node_tree.links

# clear default nodes
nodes.clear()

# create emission node
emission = nodes.new(type='ShaderNodeEmission')
emission.location = (0, 0)
emission.inputs['Color'].default_value = (0.0, 0.0, 1.0, 1.0)  # pure blue
emission.inputs['Strength'].default_value = 70.0

# create material output node
output = nodes.new(type='ShaderNodeOutputMaterial')
output.location = (200, 0)

# link emission to output
links.new(emission.outputs['Emission'], output.inputs['Surface'])

# assign material to the curve
curve_obj.data.materials.append(mat)

# optional: set origin to geometry center
bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='MEDIAN')

print("Lorenz attractor curve created with bevel depth 0.002 m, Subsurf(4), and blue emission (strength 70).")
