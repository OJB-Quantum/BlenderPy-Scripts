# cow_to_sphere_shape_keys.py
'''
Authored by Onri Jay Benally (2025)
Open Access (CC-BY-4.0)
'''

import bpy
import math
import os
import tempfile
import urllib.request
from mathutils import Vector

# ------------------------------------------------------------
# Utilities
# ------------------------------------------------------------
def download(url: str, dst_path: str) -> str:
    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
    if not os.path.exists(dst_path) or os.path.getsize(dst_path) == 0:
        print(f"Downloading: {url}")
        urllib.request.urlretrieve(url, dst_path)
    else:
        print(f"Using cached file: {dst_path}")
    return dst_path

def import_obj(obj_path: str):
    # Track objects to find what the importer adds
    before = set(bpy.data.objects)
    # Prefer new importer if present
    if hasattr(bpy.ops.wm, "obj_import"):
        res = bpy.ops.wm.obj_import(filepath=obj_path)
    else:
        res = bpy.ops.import_scene.obj(filepath=obj_path)
    if 'FINISHED' not in res:
        raise RuntimeError("OBJ import failed.")
    after = set(bpy.data.objects)
    new_objs = [o for o in after - before if bpy.data.objects.get(o.name)]
    # If multiple pieces come in, join them into one mesh
    mesh_objs = [o for o in new_objs if o.type == 'MESH']
    if not mesh_objs:
        raise RuntimeError("No MESH objects imported from OBJ.")
    bpy.ops.object.select_all(action='DESELECT')
    for o in mesh_objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = mesh_objs[0]
    if len(mesh_objs) > 1:
        bpy.ops.object.join()
    cow = bpy.context.view_layer.objects.active
    cow.name = "Cow"
    return cow

def shade_smooth(obj: bpy.types.Object):
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    try:
        bpy.ops.object.shade_smooth()
    except Exception:
        pass
    if obj.data and hasattr(obj.data, "use_auto_smooth"):
        obj.data.use_auto_smooth = True

def apply_x90_upright(obj: bpy.types.Object):
    # Rotate 90 degrees around X to "stand up", then apply rotation & scale
    obj.rotation_euler[0] += math.radians(90.0)
    bpy.context.view_layer.update()
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)

def bbox_center_and_longest_extent(obj: bpy.types.Object):
    # Works in object-local space (rotation/scale already applied)
    bb = obj.bound_box  # 8 local-space corners
    xs = [v[0] for v in bb]
    ys = [v[1] for v in bb]
    zs = [v[2] for v in bb]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    minz, maxz = min(zs), max(zs)
    center = Vector(((minx + maxx) * 0.5, (miny + maxy) * 0.5, (minz + maxz) * 0.5))
    dx, dy, dz = (maxx - minx), (maxy - miny), (maxz - minz)
    longest = max(dx, dy, dz)
    return center, float(longest)

def ensure_basis_and_new_shapekey(obj: bpy.types.Object, key_name: str):
    # Ensure there's a Basis; add our target shape key
    if not obj.data.shape_keys:
        obj.shape_key_add(name="Basis", from_mix=False)
    elif "Basis" not in obj.data.shape_keys.key_blocks:
        obj.shape_key_add(name="Basis", from_mix=False)
    new_key = obj.shape_key_add(name=key_name, from_mix=False)
    return obj.data.shape_keys.key_blocks["Basis"], new_key

def fill_sphere_shapekey(obj: bpy.types.Object, key_name: str = "SphereMorph"):
    basis_key, sphere_key = ensure_basis_and_new_shapekey(obj, key_name)
    center, longest = bbox_center_and_longest_extent(obj)
    radius = 0.5 * longest
    eps = 1e-12

    # Write the spherical positions into the target key
    for i, v_basis in enumerate(basis_key.data):
        p = Vector(v_basis.co)
        d = p - center
        n = d.length
        if n > eps:
            p_new = center + (d / n) * radius
        else:
            # Degenerate case: put this point on +X of the sphere
            p_new = center + Vector((radius, 0.0, 0.0))
        sphere_key.data[i].co = p_new

    # Keep the new key relative to Basis
    sphere_key.value = 0.0
    sphere_key.slider_min = 0.0
    sphere_key.slider_max = 1.0
    print(f"Filled shape key '{key_name}' with a radius {radius:.4f} sphere.")

def add_camera_and_light(target_obj: bpy.types.Object):
    center, longest = bbox_center_and_longest_extent(target_obj)
    r = 0.5 * longest

    # Camera
    bpy.ops.object.camera_add(location=(center.x, center.y - 3.0 * r, center.z + 0.6 * r))
    cam = bpy.context.object

    # Aim camera at the cow
    direction = (center - cam.location)
    cam.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()

    # Light
    bpy.ops.object.light_add(type='AREA',
                             location=(center.x + 2.5 * r, center.y + 2.5 * r, center.z + 2.0 * r))
    light = bpy.context.object
    light.data.energy = 1500.0
    light.data.size = 1.5 * r

def animate_morph(obj: bpy.types.Object, key_name: str = "SphereMorph",
                  f0: int = 1, f1: int = 60, start_value: float = 0.0, end_value: float = 1.0):
    key = obj.data.shape_keys.key_blocks.get(key_name)
    if not key:
        raise RuntimeError(f"Missing shape key '{key_name}' to animate.")
    key.value = start_value
    key.keyframe_insert(data_path="value", frame=f0)
    key.value = end_value
    key.keyframe_insert(data_path="value", frame=f1)
    print(f"Inserted keyframes for '{key_name}' from frame {f0} to {f1}.")

# ------------------------------------------------------------
# Main
# ------------------------------------------------------------
def main():
    # Optional: collect into its own collection
    coll_name = "CowMorphDemo"
    coll = bpy.data.collections.get(coll_name) or bpy.data.collections.new(coll_name)
    if coll.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(coll)

    # Download OBJ
    url = "https://raw.githubusercontent.com/alecjacobson/common-3d-test-models/master/data/cow.obj"
    obj_path = os.path.join(tempfile.gettempdir(), "cow.obj")
    download(url, obj_path)

    # Import
    cow = import_obj(obj_path)
    # Move it into the demo collection for tidiness
    if cow.users_collection:
        for c in cow.users_collection:
            c.objects.unlink(cow)
    coll.objects.link(cow)
    bpy.context.view_layer.objects.active = cow
    cow.select_set(True)

    # Stand upright, smooth shading
    apply_x90_upright(cow)
    shade_smooth(cow)

    # Build sphere shape key (diameter = cow's longest dimension)
    fill_sphere_shapekey(cow, key_name="SphereMorph")

    # Simple camera+light and a short morph animation
    add_camera_and_light(cow)
    animate_morph(cow, "SphereMorph", f0=1, f1=60, start_value=0.0, end_value=1.0)

    # Frame range and a friendly note
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = 60
    print("Done. Press Play to watch Cow → Sphere via the 'SphereMorph' shape key.")

if __name__ == "__main__":
    main()
