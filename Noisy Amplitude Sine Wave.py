# Authored by Onri Jay Benally (2025).
# This code is open source and open access.

import bpy
import math
import numpy as np

# -------------------------------------------------
# 1.  SET UP GPU FOR RENDERING (Cycles + CUDA)
# -------------------------------------------------
bpy.context.scene.render.engine = 'CYCLES'
prefs = bpy.context.preferences
cycles_prefs = prefs.addons['cycles'].preferences
cycles_prefs.compute_device_type = 'CUDA'                     # NVIDIA cards
for dev in cycles_prefs.devices:
    dev.use = True                                            # enable all CUDA devices
bpy.context.scene.cycles.device = 'GPU'
bpy.context.scene.cycles.feature_set = 'SUPPORTED'            # or 'EXPERIMENTAL' if you like

# -------------------------------------------------
# 2.  CREATE THE BASE CURVE (POLY LINE)
# -------------------------------------------------
# parameters
samples        = 1024            # points along X
length_x       = 12.5664        # 4π ~ two visible periods
base_amp       = 1.0            # initial amplitude before noise mod
frequency      = 5.0            # angular frequency multiplier

# generate vertices
x_vals = np.linspace(-length_x/2, length_x/2, samples)
verts  = [(float(x),
           float(base_amp * math.sin(frequency * x)),  # tmp Y, overridden in GeoNodes
           0.0)
          for x in x_vals]

# build curve object
curve_data = bpy.data.curves.new('SineCurve', type='CURVE')
curve_data.dimensions = '3D'
polyline = curve_data.splines.new('POLY')
polyline.points.add(len(verts)-1)
for p, co in zip(polyline.points, verts):
    p.co = (co[0], co[1], co[2], 1)          # (x, y, z, w)

curve_obj = bpy.data.objects.new('SineWave', curve_data)
bpy.context.collection.objects.link(curve_obj)

# bevel & resolution
curve_data.bevel_depth   = 0.005             # 2 mm radius
curve_data.resolution_u  = 8                 # smoother curve bevel
curve_data.bevel_resolution = 3

# -------------------------------------------------
# 3.  GEOMETRY NODES – animate sine with noise
#      4.3-compatible (uses nodetree.interface)
# -------------------------------------------------
gn_tree = bpy.data.node_groups.new('SineWave_Geo', 'GeometryNodeTree')
mod = curve_obj.modifiers.new(name='GN_SineWave', type='NODES')
mod.node_group = gn_tree
nodes, links = gn_tree.nodes, gn_tree.links
nodes.clear()

# ---------  create Group interface sockets first
iface = gn_tree.interface
iface.new_socket(name='Geometry', in_out='INPUT',  socket_type='NodeSocketGeometry')
iface.new_socket(name='Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')

# ---------  convenience helper
def n(ntype, **kwargs):
    node = nodes.new(ntype)
    for k, v in kwargs.items():
        setattr(node, k, v)
    return node

# mandatory I/O nodes
grp_in  = n('NodeGroupInput')
grp_out = n('NodeGroupOutput')

# all other nodes
pos       = n('GeometryNodeInputPosition')
sepxyz    = n('ShaderNodeSeparateXYZ')
freq_mul  = n('ShaderNodeMath',        operation='MULTIPLY', label='frequency')
scene_t   = n('GeometryNodeInputSceneTime')
phase_add = n('ShaderNodeMath',        operation='ADD')
sine_fn   = n('ShaderNodeMath',        operation='SINE')
combine   = n('ShaderNodeCombineXYZ')
set_pos   = n('GeometryNodeSetPosition')
noise4d   = n('ShaderNodeTexNoise',    noise_dimensions='4D')
vec_comb  = n('ShaderNodeCombineXYZ')
mult_amp  = n('ShaderNodeMath',        operation='MULTIPLY', label='noise × sin')

# links – identical logic as before
links.new(pos.outputs['Position'],      sepxyz.inputs[0])
links.new(sepxyz.outputs['X'],          freq_mul.inputs[0]);   freq_mul.inputs[1].default_value = frequency
links.new(freq_mul.outputs[0],          phase_add.inputs[0])
links.new(scene_t.outputs['Seconds'],   phase_add.inputs[1])
links.new(phase_add.outputs[0],         sine_fn.inputs[0])
links.new(sepxyz.outputs['X'],          vec_comb.inputs['X'])
links.new(scene_t.outputs['Seconds'],   vec_comb.inputs['Z'])
links.new(vec_comb.outputs['Vector'],   noise4d.inputs['Vector'])
links.new(sine_fn.outputs[0],           mult_amp.inputs[0])
links.new(noise4d.outputs['Fac'],       mult_amp.inputs[1])
links.new(mult_amp.outputs[0],          combine.inputs['Y'])
links.new(combine.outputs['Vector'],    set_pos.inputs['Offset'])
links.new(pos.outputs['Position'],      set_pos.inputs['Position'])
links.new(grp_in.outputs['Geometry'],   set_pos.inputs['Geometry'])
links.new(set_pos.outputs['Geometry'],  grp_out.inputs['Geometry'])
