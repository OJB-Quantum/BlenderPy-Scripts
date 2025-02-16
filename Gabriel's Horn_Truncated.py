import bpy
import numpy as np

def create_gabriels_horn():
    # Define x values from 1 to 20 (finite truncation for visualization)
    x = np.linspace(1, 20, 100) # Adjust these values to set how long you want Gabriel's horn to be
    theta = np.linspace(0, 2 * np.pi, 50)
    
    X, T = np.meshgrid(x, theta)
    Y = 1 / X
    Z = Y * np.sin(T)
    Y = Y * np.cos(T)
    
    vertices = [(float(X[i, j]), float(Y[i, j]), float(Z[i, j])) for i in range(X.shape[0]) for j in range(X.shape[1])]
    faces = []
    
    for i in range(len(theta) - 1):
        for j in range(len(x) - 1):
            v1 = i * len(x) + j
            v2 = v1 + 1
            v3 = v1 + len(x)
            v4 = v3 + 1
            faces.append((v1, v2, v4, v3))
    
    # Create mesh and object
    mesh = bpy.data.meshes.new("GabrielsHorn")
    obj = bpy.data.objects.new("GabrielsHorn", mesh)
    bpy.context.collection.objects.link(obj)
    
    # Set mesh data
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    
    # Add subdivision surface modifier
    mod = obj.modifiers.new(name="Subdivision", type='SUBSURF')
    mod.levels = 3  # Set 3 subdivisions
    mod.render_levels = 3
    
    # Apply transformations
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.shade_smooth()

# Run the function
create_gabriels_horn()
