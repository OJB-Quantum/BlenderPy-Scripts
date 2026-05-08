# Random-timed 180° flips around X, baked as keyframes (render-safe).
# Also flips emission color: Blue when up, Red when down (both Strength=200).
# Blender 4.x compatible.

"""
Authored by Onri Jay Benally (2026)

Open Access (CC-BY-4.0)
"""

import bpy
import math, random

# ---------------- User controls ----------------
ARROW_NAME      = "Arrow"     # Reuse if it exists; else a simple arrow mesh is built
FPS_DEFAULT     = 24          # Used only if scene fps is unset
START_FRAME     = 1
END_SECONDS     = 20          # animation length if scene.frame_end is small

# Flip timing
DISTRIBUTION    = "uniform"   # "uniform" or "exponential"
DWELL_MIN_S     = 0.8         # min hold time before a flip (seconds)
DWELL_MAX_S     = 2.2         # max hold time before a flip (seconds)
MEAN_DWELL_S    = 1.4         # used if DISTRIBUTION == "exponential"
FLIP_FRAMES     = 10          # number of frames to rotate 180° (linear)

# Colors & emission
MAT_NAME        = "Arrow_Emit_UpDown"
EMIT_STRENGTH   = 200.0
UP_COLOR        = (0.12, 0.45, 1.00, 1.0)  # blue when arrow points +Z
DOWN_COLOR      = (1.00, 0.12, 0.12, 1.0)  # red  when arrow points -Z

# Reproducibility
RNG_SEED        = 12345
# ------------------------------------------------


# ---------- Build or reuse a simple arrow mesh ----------
def get_or_build_arrow(name=ARROW_NAME):
    obj = bpy.data.objects.get(name)
    if obj and obj.type == 'MESH':
        return obj

    # Shaft
    bpy.ops.object.select_all(action='DESELECT')
    bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=0.05, depth=1.5, location=(0,0,0))
    shaft = bpy.context.active_object
    shaft.name = name + "_Shaft"

    # Cone head at +Z
    z_top = 1.5/2.0
    bpy.ops.mesh.primitive_cone_add(vertices=32, radius1=0.18, radius2=0.0, depth=0.6,
                                    location=(0,0, z_top + 0.6/2.0))
    cone = bpy.context.active_object
    cone.name = name + "_Cone"

    # Join
    shaft.select_set(True); cone.select_set(True)
    bpy.context.view_layer.objects.active = shaft
    bpy.ops.object.join()
    arrow = bpy.context.active_object
    arrow.name = name
    bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
    arrow.location = (0,0,0)
    arrow.rotation_mode = 'XYZ'
    return arrow


# ---------- Utility: clear X-rotation animation ----------
def clear_x_rotation_animation(obj):
    # Remove driver (if any)
    try:
        obj.driver_remove('rotation_euler', 0)
    except Exception:
        pass

    # Remove F-Curve on rotation_euler[0]
    ad = obj.animation_data
    if ad and ad.action:
        fcu = ad.action.fcurves.find('rotation_euler', index=0)
        if fcu:
            ad.action.fcurves.remove(fcu)
    # (fcurve removal approach per API/answers)  # docs/QA
    # https://blender.stackexchange.com/q/194438  (find/remove fcurves)  # noqa


# ---------- Keyframe helper with interpolation ----------
def insert_x_key(obj, frame, radians, interp='CONSTANT'):
    """
    Insert a keyframe on rotation_euler[0] at 'frame' with value 'radians',
    then set this keyframe's interpolation to CONSTANT or LINEAR.
    """
    obj.rotation_mode = 'XYZ'
    rot = list(obj.rotation_euler)
    rot[0] = float(radians)
    obj.rotation_euler = rot
    obj.keyframe_insert(data_path="rotation_euler", index=0, frame=frame)

    # Grab the fcurve and set this keyframe's interpolation
    fcu = obj.animation_data.action.fcurves.find("rotation_euler", index=0)
    if fcu:
        # find the keyframe point at 'frame'
        kpt = None
        for kp in fcu.keyframe_points:
            if abs(kp.co[0] - frame) < 1e-4:
                kpt = kp
                break
        if kpt:
            # Interpolation per keyframe is standard; CONSTANT holds, LINEAR gives straight ramp.
            # (See manual & API)  # noqa
            # https://docs.blender.org/manual/en/latest/animation/keyframes/introduction.html
            # https://docs.blender.org/api/current/bpy.types.Keyframe.html
            kpt.interpolation = 'CONSTANT' if interp.upper().startswith('CON') else 'LINEAR'


# ---------- Random dwell sampler ----------
def sample_dwell_seconds():
    if DISTRIBUTION.lower().startswith('exp'):
        # Exponential with mean MEAN_DWELL_S
        lam = 1.0 / max(1e-6, MEAN_DWELL_S)
        x = random.expovariate(lam)
        # Clamp to [DWELL_MIN_S, DWELL_MAX_S] so flips are human-readable
        return max(DWELL_MIN_S, min(DWELL_MAX_S, x))
    else:
        return random.uniform(DWELL_MIN_S, DWELL_MAX_S)


# ---------- Bake random flip schedule to keyframes ----------
def bake_random_flips(obj, start_f, end_f, fps, flip_frames=FLIP_FRAMES):
    clear_x_rotation_animation(obj)

    random.seed(RNG_SEED)
    angle_up, angle_down = 0.0, math.pi
    current = angle_up

    # Initial hold at START
    insert_x_key(obj, start_f, current, interp='CONSTANT')
    f = start_f

    while True:
        dwell_s = sample_dwell_seconds()
        flip_start = int(round(f + dwell_s * fps))
        if flip_start >= end_f:
            break

        # Start of transition: keep current angle, but set this keyframe's segment to LINEAR
        insert_x_key(obj, flip_start, current, interp='LINEAR')

        # End of transition: arrive at the toggled angle, then hold (CONSTANT) from here
        flip_end = min(flip_start + flip_frames, end_f)
        current = angle_down if abs(current - angle_up) < 1e-9 else angle_up
        insert_x_key(obj, flip_end, current, interp='CONSTANT')

        f = flip_end  # continue from here


# ---------- Emission material (blue when up, red when down) ----------
def build_or_update_updown_material(obj):
    mat = bpy.data.materials.get(MAT_NAME) or bpy.data.materials.new(MAT_NAME)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()

    n_out = nt.nodes.new("ShaderNodeOutputMaterial"); n_out.location = (520, 0)
    n_em  = nt.nodes.new("ShaderNodeEmission");        n_em.location  = (260, 0)
    n_em.inputs["Strength"].default_value = EMIT_STRENGTH

    n_mix = nt.nodes.new("ShaderNodeMixRGB");          n_mix.location = (20, 0)
    n_mix.blend_type = 'MIX'; n_mix.use_clamp = True
    n_mix.inputs["Color1"].default_value = DOWN_COLOR  # Fac=0 → red (down)
    n_mix.inputs["Color2"].default_value = UP_COLOR    # Fac=1 → blue (up)

    n_val = nt.nodes.new("ShaderNodeValue");           n_val.location = (-220, 0)
    n_val.name = "FlipFacVal"; n_val.outputs[0].default_value = 0.0

    nt.links.new(n_val.outputs[0], n_mix.inputs[0])
    nt.links.new(n_mix.outputs["Color"], n_em.inputs["Color"])
    nt.links.new(n_em.outputs["Emission"], n_out.inputs["Surface"])

    # Assign material
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)

    # Drive the Value node from the *actual rotation* (robust for render):
    # Fac = (cos(rotation_euler.x) > 0) -> 1 when up, 0 when down
    path = f'nodes["{n_val.name}"].outputs[0].default_value'
    try:
        nt.driver_remove(path)
    except Exception:
        pass
    fcu = nt.driver_add(path)
    drv = fcu.driver; drv.type = 'SCRIPTED'
    v = drv.variables.new(); v.name = "rx"; v.type = 'SINGLE_PROP'
    v.targets[0].id = obj
    v.targets[0].data_path = 'rotation_euler[0]'
    drv.expression = 'cos(rx) > 0'
    # Driving a shader Value with an object property is a standard pattern. :contentReference[oaicite:2]{index=2}


# ---------- Optional: Cycles and world for nice glow ----------
def setup_cycles_and_world(samples=50):
    scn = bpy.context.scene
    scn.render.engine = 'CYCLES'
    scn.cycles.samples = samples
    scn.cycles.use_adaptive_sampling = False
    # Prefer GPU if available; harmless if not
    try:
        prefs = bpy.context.preferences.addons['cycles'].preferences
        for backend in ('OPTIX', 'CUDA', 'HIP', 'METAL'):
            try:
                prefs.compute_device_type = backend
                try: prefs.get_devices()
                except Exception: pass
                for d in getattr(prefs, "devices", []): d.use = True
                scn.cycles.device = 'GPU'
                break
            except Exception:
                continue
    except Exception:
        scn.cycles.device = 'CPU'

    # Dark background for emission
    world = scn.world or bpy.data.worlds.new("World")
    scn.world = world; world.use_nodes = True
    bg = next((n for n in world.node_tree.nodes if n.type == 'BACKGROUND'),
              world.node_tree.nodes.new("ShaderNodeBackground"))
    bg.inputs["Color"].default_value = (0,0,0,1)
    bg.inputs["Strength"].default_value = 0.0


# ===================== Run =====================
arrow = get_or_build_arrow()

# Clean any previous “random rate” handlers/drivers you may have from earlier iterations
try:
    for h in list(bpy.app.handlers.frame_change_post):
        if getattr(h, "__name__", "") in {"sync_freq_rand_handler"}:
            bpy.app.handlers.frame_change_post.remove(h)
except Exception:
    pass

# Bake random flips
scene = bpy.context.scene
fps = scene.render.fps or FPS_DEFAULT
scene.frame_start = START_FRAME
scene.frame_end = max(scene.frame_end, int(END_SECONDS * fps))

bake_random_flips(arrow, START_FRAME, scene.frame_end, fps, flip_frames=FLIP_FRAMES)

# Emission color tied to actual rotation (render-safe)
build_or_update_updown_material(arrow)

# Optional render setup
setup_cycles_and_world(samples=50)

print("Random flip schedule baked. Scrub or render: arrow flips 180° at random times.")
