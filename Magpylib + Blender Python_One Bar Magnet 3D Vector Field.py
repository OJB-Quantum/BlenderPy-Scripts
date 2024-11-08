# How to use the magpylib library in Blender by Onri Jay Benally
# Copy this script into your Blender Python scripting window
# First open a terminal or command prompt and run, given that you have pip and Python installed locally: pip install magpylib
# After installing, find the path to your Python packages. To locate it, run the following in your terminal or command prompt: python -m site --user-site
# Open Blender and run this script in the Scripting Editor or Blender's Python Console to add the path: import sys
# sys.path.append("<path result from the 2nd step>")
# import magpylib
# print("magpylib is successfully imported!")

import sys
sys.path.append(r"C:\Users\ojbsn\AppData\Roaming\Python\Python312\site-packages") # Replace address or path that is in quotes with the address from the 2nd step mentioned above

# Test import
try:
    import magpylib
    print("magpylib is successfully imported!")
except ImportError:
    print("magpylib import failed.")



import bpy
import magpylib as magpy
import numpy as np
from mathutils import Vector

# Define the bar magnet as a cuboid with specific magnetization and dimensions
bar_magnet = magpy.magnet.Cuboid(magnetization=(1500, 0, 0), dimension=(3, 1, 1))

# Create a grid of points around the magnet to compute the magnetic field
x = np.linspace(-5, 5, 15)
y = np.linspace(-5, 5, 15)
z = np.linspace(-5, 5, 15)
X, Y, Z = np.meshgrid(x, y, z)
positions = np.column_stack((X.ravel(), Y.ravel(), Z.ravel()))

# Calculate the magnetic field at each point in the grid
B = bar_magnet.getB(positions).reshape(X.shape + (3,))

# Clear existing objects in the scene
bpy.ops.object.select_all(action='DESELECT')
bpy.ops.object.select_by_type(type='MESH')
bpy.ops.object.delete()

# Create cones at each grid point
for i, (pos, field) in enumerate(zip(positions, B.reshape(-1, 3))):
    # Create a cone
    bpy.ops.mesh.primitive_cone_add(vertices=32, radius1=0.1, depth=0.5, enter_editmode=False)
    cone = bpy.context.object
    cone.name = f"Cone_{i}"

    # Set cone location
    cone.location = Vector(pos)

    # Orient the cone along the magnetic field direction
    field_vector = Vector(field)
    if field_vector.length != 0:
        # Align the cone to point along the field vector
        field_vector.normalize()
        rotation = field_vector.to_track_quat('Z', 'Y').to_euler()
        cone.rotation_euler = rotation

    # Optionally, scale based on field magnitude (for visual effect)
    cone.scale.z *= field_vector.length  # You can adjust this scaling factor as needed

# Update the scene
bpy.context.view_layer.update()
