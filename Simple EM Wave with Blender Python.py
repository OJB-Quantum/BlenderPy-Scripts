'''
Part 1:
Enter this prompt into a code generator:
Please use matplotlib in 3D to plot 2 orthogonal sinusoidal waves, for the electromagnetic wave, with a period of 6 pi. No grid lines, plot labels, or titles. It should not look like a spiral.
_________________
Part 2:
Enter this prompt into a code generator:
Based on the following script, please generate a Blender python script that creates a transverse electromagnetic wave using curve tools in Blender, make sure the waves are rotated 90 degrees from each other, make the bevel round depth of both curves to be 0.02 m and increase the wave amplitude by 2, make both objects have an emission with their respective colors and set the strength to 50: 
<Insert the code that was generated in Part 1>

# See Part 3 at the end...

'''

import bpy
import math
import numpy as np

# Parameters
t = np.linspace(0, 900 * np.pi, 30000) # The value after np.pi is the number of data points
amplitude = 2
x = amplitude * np.sin(t)  # Electric field
y = amplitude * np.cos(t)  # Magnetic field
z = t  # Propagation direction

# Create the curve for the electric field
electric_curve = bpy.data.curves.new(name="ElectricFieldCurve", type='CURVE')
electric_curve.dimensions = '3D'
electric_curve.bevel_depth = 0.02  # Set bevel depth

electric_spline = electric_curve.splines.new(type='POLY')
electric_spline.points.add(len(t) - 1)
for i, (xi, zi) in enumerate(zip(x, z)):
    electric_spline.points[i].co = (zi, xi, 0, 1)

electric_obj = bpy.data.objects.new("ElectricField", electric_curve)
bpy.context.collection.objects.link(electric_obj)

# Create the curve for the magnetic field
magnetic_curve = bpy.data.curves.new(name="MagneticFieldCurve", type='CURVE')
magnetic_curve.dimensions = '3D'
magnetic_curve.bevel_depth = 0.02  # Set bevel depth

magnetic_spline = magnetic_curve.splines.new(type='POLY')
magnetic_spline.points.add(len(t) - 1)
for i, (yi, zi) in enumerate(zip(y, z)):
    magnetic_spline.points[i].co = (zi, 0, yi, 1)

magnetic_obj = bpy.data.objects.new("MagneticField", magnetic_curve)
bpy.context.collection.objects.link(magnetic_obj)

# Create materials with emission
def create_emission_material(name, color, strength):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    nodes.clear()
    output_node = nodes.new(type="ShaderNodeOutputMaterial")
    emission_node = nodes.new(type="ShaderNodeEmission")
    emission_node.inputs["Color"].default_value = (*color, 1)  # Set color
    emission_node.inputs["Strength"].default_value = strength  # Set strength
    links.new(emission_node.outputs["Emission"], output_node.inputs["Surface"])
    return mat

# Assign materials
electric_material = create_emission_material("ElectricFieldMaterial", (1, 0, 0), 50)  # Red
magnetic_material = create_emission_material("MagneticFieldMaterial", (0, 0, 1), 50)  # Blue

electric_obj.data.materials.append(electric_material)
magnetic_obj.data.materials.append(magnetic_material)

'''
_________________
Part 3:
Apply the following manually to save prompting complexity (performed in Blender):
- Enable raytracing with the Eevee render engine
- Enable Raytraced Emission under the Material Properties tab
- Apply glare filter under the Compositing tab (enable Use Nodes first)
- Change the world background color to black

'''