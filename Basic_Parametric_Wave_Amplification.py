```
Authored by Onri Jay Benally (2025)
Open Access (CC-BY-4.0)
```

import bpy
import math

# ----------------- Parameters -----------------
OBJ_NAME            = "WaveCurve"
MAT_NAME            = "Wave_Emission_Blue"
COLL_NAME           = "WaveScene"
N_POINTS            = 1000
X_MIN, X_MAX        = 0.0, 40.0
A0                  = 0.2
ALPHA               = 0.1
K                   = 2.0
PHASE_SPEED_RAD_F   = 0.15
CURVE_BEVEL_DEPTH   = 0.03
CURVE_RESOLUTION_U  = 64
FRAME_START, FRAME_END, FPS = 1, 240, 24
CAMERA_DIST         = 25.0
WORLD_BG_STRENGTH   = 0.0
SAMPLES             = 50
EMISSION_COLOR      = (0.12, 0.45, 1.00, 1.0)
EMISSION_STRENGTH   = 200.0
OUT_MOV             = "//wave_phase_anim.mp4"
# ------------------------------------------------

# Try numpy for speed; fall back to Python
try:
    import numpy as np
    USE_NUMPY = True
except Exception:
    USE_NUMPY = False

# ---------- Collections ----------
def ensure_collection(name):
    coll = bpy.data.collections.get(name)
    if coll is None:
        coll = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(coll)
    return coll

coll = ensure_collection(COLL_NAME)
root = bpy.context.scene.collection

# ---------- Cycles GPU (robust) ----------
def setup_cycles_gpu(samples=SAMPLES):
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = samples
    scene.cycles.use_adaptive_sampling = False
    scene.cycles.device = 'GPU'  # use GPU if available
    prefs = bpy.context.preferences.addons.get('cycles').preferences

    # Try common backends, refresh devices, enable all
    for backend in ('OPTIX', 'CUDA', 'HIP', 'METAL'):
        try:
            prefs.compute_device_type = backend
            # Refresh device list; API naming varies by version
            try:
                prefs.get_devices()
            except Exception:
                try:
                    prefs.get_devices_for_type(backend)
                except Exception:
                    pass
            for d in getattr(prefs, "devices", []):
                d.use = True
            break
        except Exception:
            continue
    # (Using compute_device_type + enabling devices is the pattern reported by users/devs.)  # noqa
    # refs: BlenderSE & dev talk threads on programmatic GPU selection
    # (compute_device_type, get_devices, enable devices). 
    # See sources in citations.

setup_cycles_gpu(SAMPLES)

# ---------- Material ----------
def get_or_create_emission_material(name, color_rgba, strength):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name=name)
        mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (300, 0)
    emi = nt.nodes.new("ShaderNodeEmission"); emi.location = (0, 0)
    emi.inputs["Color"].default_value = color_rgba
    emi.inputs["Strength"].default_value = float(strength)
    nt.links.new(emi.outputs["Emission"], out.inputs["Surface"])
    return mat

mat = get_or_create_emission_material(MAT_NAME, EMISSION_COLOR, EMISSION_STRENGTH)

# ---------- Curve ----------
def get_or_create_curve(name, bevel_depth, resolution_u, material):
    obj = bpy.data.objects.get(name)
    if obj and obj.type != 'CURVE':
        obj.name = name + "_old"
        obj = None
    if obj is None:
        curve_data = bpy.data.curves.new(name=name, type='CURVE')
        curve_data.dimensions = '3D'
        curve_data.bevel_depth = bevel_depth
        curve_data.bevel_resolution = 8
        curve_data.resolution_u = resolution_u
        spline = curve_data.splines.new('POLY')
        spline.points.add(N_POINTS - 1)
        obj = bpy.data.objects.new(name, curve_data)
    else:
        curve_data = obj.data
        curve_data.bevel_depth = bevel_depth
        curve_data.bevel_resolution = 8
        curve_data.resolution_u = resolution_u
        if len(curve_data.splines) == 0 or curve_data.splines[0].type != 'POLY':
            curve_data.splines.clear()
            spline = curve_data.splines.new('POLY')
            spline.points.add(N_POINTS - 1)
        else:
            spline = curve_data.splines[0]
            if len(spline.points) != N_POINTS:
                curve_data.splines.clear()
                spline = curve_data.splines.new('POLY')
                spline.points.add(N_POINTS - 1)
    # Material
    if material is not None:
        obj.data.materials.clear()
        obj.data.materials.append(material)
    return obj

curve_obj = get_or_create_curve(OBJ_NAME, CURVE_BEVEL_DEPTH, CURVE_RESOLUTION_U, mat)

# AFTER (correct: membership by NAME)
if curve_obj.name not in coll.objects:
    coll.objects.link(curve_obj)

if curve_obj.name in root.objects:
    try:
        root.objects.unlink(curve_obj)
    except RuntimeError:
        pass  # harmless if concurrently unlinked

curve_obj.location = (0.0, 0.0, 0.0)

# ---------- Sampling grid ----------
if USE_NUMPY:
    x_grid = np.linspace(X_MIN, X_MAX, N_POINTS, dtype=np.float64)
else:
    step = (X_MAX - X_MIN) / (N_POINTS - 1)
    x_grid = [X_MIN + i * step for i in range(N_POINTS)]

def envelope(x):
    return (A0 * (math.e ** (ALPHA * x))) if not USE_NUMPY else A0 * np.exp(ALPHA * x)

def y_of(x, phase):
    return envelope(x) * (math.sin(K * x + phase) if not USE_NUMPY else np.sin(K * x + phase))

# ---------- Animate phase via frame handler ----------
def update_curve_for_frame(scene):
    frame = max(scene.frame_current, 1)
    phase = PHASE_SPEED_RAD_F * (frame - FRAME_START)
    obj = bpy.data.objects.get(OBJ_NAME)
    if not obj or obj.type != 'CURVE':
        return
    spline = obj.data.splines[0]
    pts = spline.points

    X_SCALE = 0.4
    X_OFFSET = - (X_MAX - X_MIN) * 0.2

    if USE_NUMPY:
        y_vals = y_of(x_grid, phase)
        for i in range(N_POINTS):
            x = X_SCALE * (x_grid[i] + X_OFFSET)
            y = float(y_vals[i])
            pts[i].co = (x, y, 0.0, 1.0)
    else:
        for i in range(N_POINTS):
            x = x_grid[i]
            y = y_of(x, phase)
            pts[i].co = (X_SCALE * (x + X_OFFSET), y, 0.0, 1.0)
    obj.data.update()

# Remove previous handler if any (re-run safe)
for h in list(bpy.app.handlers.frame_change_pre):
    if getattr(h, "__name__", "") == "update_curve_for_frame":
        bpy.app.handlers.frame_change_pre.remove(h)
bpy.app.handlers.frame_change_pre.append(update_curve_for_frame)

# ---------- Camera & world ----------
def ensure_camera():
    for ob in coll.objects:
        if ob.type == 'CAMERA':
            bpy.context.scene.camera = ob
            return ob
    cam_data = bpy.data.cameras.new("WaveCam")
    cam = bpy.data.objects.new("WaveCam", cam_data)
    coll.objects.link(cam)
    cam.location = (0.0, -CAMERA_DIST, 7.0)
    cam.rotation_euler = (math.radians(80.0), 0.0, 0.0)
    cam.data.lens = 60.0
    bpy.context.scene.camera = cam
    return cam

ensure_camera()

world = bpy.context.scene.world or bpy.data.worlds.new("World")
bpy.context.scene.world = world
world.use_nodes = True
wn = world.node_tree
bg = next((n for n in wn.nodes if n.type == 'BACKGROUND'), wn.nodes.new("ShaderNodeBackground"))
bg.inputs["Color"].default_value = (0.0, 0.0, 0.0, 1.0)
bg.inputs["Strength"].default_value = WORLD_BG_STRENGTH

# ---------- Render / timeline ----------
scene = bpy.context.scene
scene.frame_start = FRAME_START
scene.frame_end   = FRAME_END
scene.render.fps  = FPS
scene.render.image_settings.file_format = 'FFMPEG'
scene.render.ffmpeg.format = 'MPEG4'
scene.render.ffmpeg.codec  = 'H264'
scene.render.ffmpeg.constant_rate_factor = 'MEDIUM'
scene.render.filepath = OUT_MOV

# Important when editing data in frame handlers during render:
scene.render.use_lock_interface = True  # avoids thread conflicts during render  # noqa

scene.frame_set(FRAME_START)
print("Wave animation ready. Render → Render Animation to produce:", OUT_MOV)
