# BEC-like collective excitations: dynamic paint (waves) + wave modifiers
# Optimized for Blender 4.5 (Cycles). Self-contained.
```
Authored by Onri Jay Benally (2025)
Open Access (CC-BY-4.0)
```

import bpy
import math
import random
from math import tau, sqrt
from dataclasses import dataclass
from typing import List, Tuple, Optional

# =========================
# SECTION 0 — CONTROL KNOBS
# =========================

@dataclass
class Knobs:
    """Top-level parameters for quick art-direction and performance tuning."""
    seed: int = 42
    fps: int = 30
    warmup_frames: int = 100
    morph_frames: int = 450

    # Lattice (physical canvas)
    grid_size: float = 20.0          # physical width/height of the plane (scene units)
    grid_subdiv: int = 256           # subdivisions per axis on the plane mesh

    use_dynamic_paint: bool = True

    # --- Primary layout/motion controls ---
    particle_count: int = 64                 # total particles (overridden if rows*cols provided)
    particle_motion_radius: float = 1.10     # per-particle wiggle radius (non-overlap enforced)
    array_density: float = 1.0               # 1.0 = densest non-overlap; 0.25 = quarter density (sparser)

    # Explicit grid size (if both set, overrides particle_count)
    array_rows: Optional[int] = None
    array_cols: Optional[int] = None

    # Visual spheres
    brush_radius: float = 0.08
    brush_altitude: float = 0.04

    # Square-array layout envelope
    # Absolute span (scene units). If set, spread does not change when grid_size changes.
    array_span_abs: Optional[float] = 8.5
    array_span_frac: float = 0.85            # fallback if array_span_abs is None
    cell_gap_frac: float = 0.10              # extra neighbor gap as a fraction of diameter
    array_jitter_frac: float = 0.04          # “almost perfect” jitter (clamped to keep non-overlap)

    # Motion and slowdown
    # NEW: smaller step interval gives clearer motion sampling; boost pre/post amplitudes; shape decay with gammas.
    wander_step: int = 8                     # NEW: more frequent keyframes for visibly smoother motion
    step_frac_of_radius: float = 0.33        # base step = this * motion radius (pre-decel)
    motion_boost_pre: float = 1.50           # NEW: multiply pre-100 step radius by this (>1 = more motion)
    motion_boost_post: float = 1.20          # NEW: multiply initial post-100 jitter by this
    noise_decay_gamma: float = 1.60          # NEW: exponent shaping how fast jitter decays (higher = steeper late)
    drift_gamma: float = 1.25                # NEW: exponent shaping drift blend (higher = slower early drift)

    decel_start: int = 100                   # begin “return-halfway” at frame 100
    decel_end: int = 450                     # almost stopped by frame 450

    # Wavelet shaping
    energy_min: float = 0.35
    energy_max: float = 1.00
    small_wave_height: float = 0.065
    small_wave_width: float = 0.65
    small_wave_narrowness: float = 1.75

    # Collective wave
    collective_height_final: float = 0.85
    collective_width: float = 2.75
    collective_narrowness: float = 1.00

    # Camera & render
    cam_dist: float = 13.0
    cam_pitch_deg: float = 56.0
    render_samples: int = 128
    noise_threshold: float = 0.010
    use_oidn: bool = True
    resolution_x: int = 1920
    resolution_y: int = 1080


K = Knobs()


# =========================
# SECTION 1 — UTILITIES
# =========================

def nuke_scene() -> None:
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False, confirm=False)
    for col in list(bpy.data.collections):
        if col.users == 0 and col.name != "Collection":
            bpy.data.collections.remove(col)
    for mat in list(bpy.data.materials):
        if mat.users == 0:
            bpy.data.materials.remove(mat)
    world = bpy.data.worlds.new("World-BEC") if not bpy.data.worlds else bpy.data.worlds[0]
    bpy.context.scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    for node in list(nt.nodes):
        nt.nodes.remove(node)
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs[0].default_value = (0.015, 0.02, 0.03, 1.0)
    bg.inputs[1].default_value = 1.0
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])


def rng(seed: int) -> random.Random:
    r = random.Random()
    r.seed(seed)
    return r


def random_point_in_disk(r: random.Random, radius: float) -> Tuple[float, float]:
    u = r.random()
    t = r.random() * tau
    rad = radius * sqrt(u)
    return rad * math.cos(t), rad * math.sin(t)


def ensure_collection(name: str) -> bpy.types.Collection:
    if name in bpy.data.collections:
        col = bpy.data.collections[name]
    else:
        col = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(col)
    return col


def set_cycles(Knobs: Knobs) -> None:
    scn = bpy.context.scene
    scn.render.engine = 'CYCLES'
    scn.render.resolution_x = Knobs.resolution_x
    scn.render.resolution_y = Knobs.resolution_y
    scn.render.fps = Knobs.fps
    scn.frame_start = 1
    scn.frame_end = 1 + Knobs.warmup_frames + Knobs.morph_frames

    scn.view_settings.view_transform = "Filmic"
    scn.view_settings.look = "Medium High Contrast"

    cy = scn.cycles
    cy.samples = Knobs.render_samples
    cy.use_adaptive_sampling = True
    cy.adaptive_threshold = Knobs.noise_threshold
    cy.use_preview_denoising = True
    cy.use_persistent_data = True

    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for dev_typ in ("OPTIX", "CUDA", "HIP", "METAL"):
            try:
                prefs.compute_device_type = dev_typ
                break
            except Exception:
                continue
        try:
            prefs.get_devices()
            for dev in prefs.devices:
                dev.use = True
        except Exception:
            pass
        cy.device = 'GPU'
    except Exception:
        cy.device = 'CPU'

    try:
        vl = scn.view_layers["View Layer"]
        vl.cycles.use_denoising = Knobs.use_oidn
    except Exception:
        pass


def keyframe_linear(owner, data_path: str, frame: int) -> None:
    """Insert a keyframe on any RNA owner (ID or non‑ID) and force linear interpolation."""
    try:
        full_path = owner.path_from_id(data_path)
    except Exception:
        full_path = data_path
    id_owner = getattr(owner, "id_data", None) or owner
    id_owner.keyframe_insert(data_path=full_path, frame=frame)
    ad = getattr(id_owner, "animation_data", None)
    if not ad or not ad.action:
        return
    for fc in ad.action.fcurves:
        if fc.data_path == full_path:
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'


# ======================================
# SECTION 2 — LATTICE MESH & MATERIALS
# ======================================

def _set_bsdf_input(bsdf_node: bpy.types.ShaderNode, candidates, value) -> bool:
    for name in candidates:
        try:
            sock = bsdf_node.inputs[name]
            sock.default_value = value
            return True
        except KeyError:
            continue
    for sock in bsdf_node.inputs:
        if sock.name in candidates:
            try:
                sock.default_value = value
                return True
            except Exception:
                pass
    print(f"[WARN] None of sockets {candidates} found on {bsdf_node.bl_label}")
    return False


def build_lattice(Knobs: Knobs) -> bpy.types.Object:
    col = ensure_collection("BEC-Lattice")
    bpy.ops.mesh.primitive_grid_add(
        x_subdivisions=Knobs.grid_subdiv,
        y_subdivisions=Knobs.grid_subdiv,
        size=Knobs.grid_size * 0.5,
        enter_editmode=False,
        location=(0.0, 0.0, 0.0),
    )
    plane = bpy.context.active_object
    plane.name = "LatticeMesh"
    col.objects.link(plane)
    for c in list(plane.users_collection):
        if c.name != col.name:
            c.objects.unlink(plane)

    bpy.ops.object.shade_smooth()
    cs = plane.modifiers.new("CorrectiveSmooth", 'CORRECTIVE_SMOOTH')
    cs.factor = 0.2
    cs.iterations = 5

    mat = bpy.data.materials.new("Mat-LatticeGrid")
    mat.use_nodes = True
    nt = mat.node_tree
    for node in list(nt.nodes):
        nt.nodes.remove(node)

    out = nt.nodes.new("ShaderNodeOutputMaterial")
    princ = nt.nodes.new("ShaderNodeBsdfPrincipled")
    mix = nt.nodes.new("ShaderNodeMixShader")
    emis = nt.nodes.new("ShaderNodeEmission")
    chk = nt.nodes.new("ShaderNodeTexChecker")
    ramp = nt.nodes.new("ShaderNodeValToRGB")

    _set_bsdf_input(princ, ("Base Color",), (0.02, 0.08, 0.12, 1.0))
    _set_bsdf_input(princ, ("Metallic",), 0.0)
    _set_bsdf_input(princ, ("Roughness",), 0.15)
    _set_bsdf_input(princ, ("Specular", "Specular IOR Level"), 0.55)
    _set_bsdf_input(princ, ("Transmission", "Transmission Weight"), 0.0)

    chk.inputs["Scale"].default_value = 40.0
    ramp.color_ramp.elements[0].position = 0.49
    ramp.color_ramp.elements[1].position = 0.51
    ramp.color_ramp.elements[0].color = (0.05, 0.08, 0.10, 1.0)
    ramp.color_ramp.elements[1].color = (0.015, 0.018, 0.02, 1.0)

    emis.inputs["Strength"].default_value = 0.25
    emis.inputs["Color"].default_value = (0.04, 0.10, 0.18, 1.0)

    nt.links.new(chk.outputs["Color"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], princ.inputs["Base Color"])
    nt.links.new(princ.outputs["BSDF"], mix.inputs[1])
    nt.links.new(emis.outputs["Emission"], mix.inputs[2])
    nt.links.new(ramp.outputs["Color"], mix.inputs["Fac"])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])

    plane.data.materials.append(mat)
    return plane


# =========================================
# SECTION 3 — DYNAMIC PAINT (optional) ON
# =========================================

def add_dynamic_paint_canvas(plane: bpy.types.Object) -> Optional[bpy.types.Modifier]:
    try:
        mod = plane.modifiers.new("DP-Canvas", 'DYNAMIC_PAINT')
        mod.ui_type = 'CANVAS'
        cvs = mod.canvas_settings.canvas_surfaces.new()
        cvs.name = "Waves"
        cvs.surface_type = 'WAVE'
        for attr, val in [
            ("use_dry_log", False),
            ("wave_speed", 1.0),
            ("wave_damping", 0.02),
            ("timescale", 1.0),
            ("clamp_wave", True),
        ]:
            if hasattr(cvs, attr):
                setattr(cvs, attr, val)
        return mod
    except Exception as e:
        print(f"[WARN] Dynamic Paint setup skipped: {e}")
        return None


def add_dynamic_paint_brush(sphere: bpy.types.Object) -> Optional[bpy.types.Modifier]:
    try:
        mod = sphere.modifiers.new("DP-Brush", 'DYNAMIC_PAINT')
        mod.ui_type = 'BRUSH'
        bs = mod.brush_settings
        if hasattr(bs, "paint_source"):
            bs.paint_source = 'MESH_VOLUME'
        if hasattr(bs, "paint_color"):
            bs.paint_color = (0.2, 0.6, 1.0)
        if hasattr(bs, "proximity_falloff"):
            bs.proximity_falloff = 'SMOOTH'
        return mod
    except Exception as e:
        print(f"[WARN] Dynamic Paint brush skipped: {e}")
        return None


# ==========================================
# SECTION 4 — WAVE MODIFIERS (wavelets, etc)
# ==========================================

def add_wave_modifier(
    obj: bpy.types.Object,
    name: str,
    height: float,
    width: float,
    narrowness: float,
    use_x: bool = True,
    use_y: bool = True,
) -> bpy.types.Modifier:
    w = obj.modifiers.new(name, 'WAVE')
    w.height = height
    w.width = width
    w.narrowness = narrowness
    w.use_x = use_x
    w.use_y = use_y
    w.use_cyclic = True
    return w


def keyframe_wave_center(w: bpy.types.Modifier, frame: int, x: float, y: float) -> None:
    w.start_position_x = x
    w.start_position_y = y
    keyframe_linear(w, "start_position_x", frame)
    keyframe_linear(w, "start_position_y", frame)


def keyframe_wave_height(w: bpy.types.Modifier, frame: int, h: float) -> None:
    w.height = h
    keyframe_linear(w, "height", frame)


# =======================================
# SECTION 5 — CAMERA, LIGHTS, COLLECTIONS
# =======================================

def add_camera(Knobs: Knobs) -> bpy.types.Object:
    col = ensure_collection("BEC-CamLight")
    cam_data = bpy.data.cameras.new("Cam-BEC")
    cam = bpy.data.objects.new("Cam-BEC", cam_data)
    col.objects.link(cam)
    phi = math.radians(Knobs.cam_pitch_deg)
    cam.location = (0.0, -Knobs.cam_dist * math.cos(phi), Knobs.cam_dist * math.sin(phi))
    cam.rotation_euler = (math.radians(90 - Knobs.cam_pitch_deg), 0.0, 0.0)
    cam.data.lens = 45.0
    bpy.context.scene.camera = cam
    return cam


def add_lights() -> None:
    col = ensure_collection("BEC-CamLight")
    bpy.ops.object.light_add(type='AREA', radius=6.0, location=(0, 0, 7.0))
    area1 = bpy.context.active_object
    area1.name = "Area-Overhead"
    col.objects.link(area1)
    for c in list(area1.users_collection):
        if c.name != col.name:
            c.objects.unlink(area1)
    area1.data.energy = 2200.0
    area1.data.size = 7.0

    bpy.ops.object.light_add(type='AREA', radius=3.0, location=(6.0, -6.0, 5.0))
    area2 = bpy.context.active_object
    area2.name = "Area-Rim"
    col.objects.link(area2)
    for c in list(area2.users_collection):
        if c.name != col.name:
            c.objects.unlink(area2)
    area2.data.energy = 1200.0
    area2.data.size = 3.5
    area2.rotation_euler = (math.radians(60.0), 0.0, math.radians(30.0))


# ==========================================
# SECTION 6 — BRUSH SPHERES & THEIR MOTIONS
# ==========================================

def make_sphere(radius: float, color: Tuple[float, float, float]) -> bpy.types.Object:
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=radius, segments=16, ring_count=8, enter_editmode=False, location=(0, 0, 0)
    )
    sp = bpy.context.active_object
    sp.name = "BrushSphere"
    mat = bpy.data.materials.new("Mat-Brush")
    mat.use_nodes = True
    nt = mat.node_tree
    for node in list(nt.nodes):
        nt.nodes.remove(node)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    emis = nt.nodes.new("ShaderNodeEmission")
    emis.inputs["Strength"].default_value = 1.5
    emis.inputs["Color"].default_value = (color[0], color[1], color[2], 1.0)
    nt.links.new(emis.outputs["Emission"], out.inputs["Surface"])
    sp.data.materials.append(mat)
    return sp


def _smoothstep01(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def _wiggle_then_return_halfway_path(
    r: random.Random,
    start_xy: Tuple[float, float],
    frames: List[int],
    base_step: float,
    max_radius: float,
    t_return_start: int,
    t_return_end: int,
    boost_pre: float,
    boost_post: float,
    noise_gamma: float,
    drift_gamma: float,
) -> List[Tuple[float, float]]:
    """Phase 1: stronger, bounded wiggle up to t_return_start.
    Phase 2: ease toward midpoint between (start) and (pos at t_return_start),
    with jitter radius decaying as (1 - w)^noise_gamma, where
    w = smoothstep(t) ** drift_gamma.
    Always clamped to the same disc D(start_xy, max_radius).
    """
    pts: List[Tuple[float, float]] = []
    x, y = start_xy

    # Ensure both key frames are present
    frame_set = set(frames)
    frame_set.add(t_return_start)
    frame_set.add(t_return_end)
    frames_sorted = sorted(frame_set)

    pos_at_start_return: Optional[Tuple[float, float]] = None

    for f in frames_sorted:
        if f <= t_return_start:
            # Stronger pre-return wiggle
            step = base_step * boost_pre
            dx, dy = random_point_in_disk(r, step)
            x += dx
            y += dy
        else:
            if pos_at_start_return is None:
                pos_at_start_return = (x, y)  # capture position at return start
            # Time in [0,1]
            t01 = (f - t_return_start) / max(1.0, (t_return_end - t_return_start))
            # Drift blend (ease-out with exponent)
            w = _smoothstep01(t01) ** drift_gamma
            mid_x = 0.5 * (start_xy[0] + pos_at_start_return[0])
            mid_y = 0.5 * (start_xy[1] + pos_at_start_return[1])
            base_x = (1.0 - w) * pos_at_start_return[0] + w * mid_x
            base_y = (1.0 - w) * pos_at_start_return[1] + w * mid_y
            # Jitter decays with exponent; slightly boosted right after 100
            jitter_amp = base_step * boost_post * ((1.0 - w) ** noise_gamma)
            jx, jy = random_point_in_disk(r, jitter_amp)
            x = base_x + jx
            y = base_y + jy

        # Clamp to personal disc
        vx = x - start_xy[0]
        vy = y - start_xy[1]
        dist = math.hypot(vx, vy)
        if dist > max_radius:
            scale = max_radius / (dist if dist > 1e-8 else 1.0)
            x = start_xy[0] + vx * scale
            y = start_xy[1] + vy * scale

        if f == t_return_start:
            pos_at_start_return = (x, y)
        if f in frames:
            pts.append((x, y))

    return pts


def _compute_rows_cols(
    n: int,
    rows_hint: Optional[int],
    cols_hint: Optional[int],
) -> Tuple[int, int, int]:
    """Resolve grid (rows, cols) and possibly adjusted N based on user hints.

    Returns:
        rows, cols, N_effective
    """
    if rows_hint and rows_hint > 0 and cols_hint and cols_hint > 0:
        rows = int(rows_hint)
        cols = int(cols_hint)
        N_eff = rows * cols
        return rows, cols, N_eff

    if cols_hint and cols_hint > 0:
        cols = int(cols_hint)
        rows = math.ceil(n / cols)
        return rows, cols, n

    if rows_hint and rows_hint > 0:
        rows = int(rows_hint)
        cols = math.ceil(n / rows)
        return rows, cols, n

    # Default: near-square
    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)
    return rows, cols, n


def add_brush_spheres_and_wavelets(
    Knobs: Knobs,
    plane: bpy.types.Object,
    use_brush: bool,
) -> Tuple[List[bpy.types.Object], List[bpy.types.Modifier], bpy.types.Modifier]:
    """Create moving brush spheres and corresponding small-wave modifiers."""
    col = ensure_collection("BEC-Emitters")
    rnd = rng(Knobs.seed)

    spheres: List[bpy.types.Object] = []
    wavelets: List[bpy.types.Modifier] = []

    total_frames = 1 + Knobs.warmup_frames + Knobs.morph_frames

    # Keyframe schedule for motion (ensure 100 and 450 are included explicitly).
    step_frames = list(range(1, Knobs.decel_end + 1, Knobs.wander_step))
    if Knobs.decel_start not in step_frames:
        step_frames.append(Knobs.decel_start)
    if Knobs.decel_end not in step_frames:
        step_frames.append(Knobs.decel_end)
    step_frames = sorted(step_frames)

    # ---- Grid size, count, density, and absolute span ----
    N_req = int(max(1, Knobs.particle_count))
    rows, cols, N_eff = _compute_rows_cols(N_req, Knobs.array_rows, Knobs.array_cols)
    if N_eff != N_req:
        print(f"[INFO] particle_count overridden by array_rows*array_cols = {rows}*{cols} = {N_eff}.")

    # Use absolute span if provided; else fall back to fraction of grid_size.
    usable_span_x = Knobs.array_span_abs if Knobs.array_span_abs is not None else (Knobs.grid_size * Knobs.array_span_frac)
    usable_span_y = Knobs.array_span_abs if Knobs.array_span_abs is not None else (Knobs.grid_size * Knobs.array_span_frac)

    # Non-overlap base pitch
    R = float(Knobs.particle_motion_radius)  # personal wiggle radius
    min_pitch = 2.0 * R * (1.0 + Knobs.cell_gap_frac)

    # Span-limited maximum pitch
    max_pitch_x = float('inf') if cols == 1 else usable_span_x / (cols - 1)
    max_pitch_y = float('inf') if rows == 1 else usable_span_y / (rows - 1)
    max_pitch_allow = min(max_pitch_x, max_pitch_y)

    # If requested radius cannot fit even at densest packing, reduce radius slightly
    if min_pitch > max_pitch_allow:
        R_old = R
        R = (max_pitch_allow / (2.0 * (1.0 + Knobs.cell_gap_frac))) * 0.98
        print(f"[INFO] particle_motion_radius reduced {R_old:.3f} -> {R:.3f} to fit {N_eff} sites within span (non-overlap).")
        min_pitch = 2.0 * R * (1.0 + Knobs.cell_gap_frac)

    # Apply density: p = p_min / sqrt(density), then clamp by span
    dens = max(1e-6, min(1.0, float(Knobs.array_density)))
    pitch_desired = min_pitch / math.sqrt(dens)
    pitch = min(pitch_desired, max_pitch_allow)
    if pitch < pitch_desired - 1e-6:
        print("[INFO] array_density clamped by array_span; increase array_span_abs or reduce particle_count/rows/cols.")

    # Center the array at (0,0)
    x0 = -0.5 * (cols - 1) * pitch
    y0 = -0.5 * (rows - 1) * pitch

    # Jitter is clamped to preserve non-overlap after perturbation
    leftover = max(0.0, 0.5 * (pitch - 2.0 * R * (1.0 + Knobs.cell_gap_frac)))
    jitter_amp = min(Knobs.array_jitter_frac * pitch, leftover) * 0.99

    # Base step relative to radius, gently capped to avoid boundary banging
    base_step = min(Knobs.step_frac_of_radius * R, 0.45 * R)

    # ---- Create emitters in grid order ----
    for i in range(N_eff):
        r_i = i // cols
        c_i = i % cols
        if r_i >= rows:
            r_i = rows - 1  # safety

        # Base grid pos with tiny jitter
        gx = x0 + c_i * pitch
        gy = y0 + r_i * pitch
        jx = rnd.uniform(-jitter_amp, jitter_amp)
        jy = rnd.uniform(-jitter_amp, jitter_amp)
        sx = gx + jx
        sy = gy + jy
        start_xy = (sx, sy)

        # Wavelet amplitude per emitter (sphere size stays constant)
        energy = Knobs.energy_min + (Knobs.energy_max - Knobs.energy_min) * rnd.random()
        h = Knobs.small_wave_height * energy

        # Wavelet modifier on the lattice
        wv = add_wave_modifier(
            plane,
            name=f"Wavelet-{i:02d}",
            height=h,
            width=Knobs.small_wave_width,
            narrowness=Knobs.small_wave_narrowness,
            use_x=True,
            use_y=True,
        )
        wavelets.append(wv)

        # Motion path: stronger early wiggle; then return-halfway with visible decay
        pts = _wiggle_then_return_halfway_path(
            r=rnd,
            start_xy=start_xy,
            frames=step_frames,
            base_step=base_step,
            max_radius=R,
            t_return_start=Knobs.decel_start,
            t_return_end=Knobs.decel_end,
            boost_pre=Knobs.motion_boost_pre,
            boost_post=Knobs.motion_boost_post,
            noise_gamma=Knobs.noise_decay_gamma,
            drift_gamma=Knobs.drift_gamma,
        )

        # Keyframe wavelet centers along the path
        for f, (px, py) in zip(step_frames, pts):
            keyframe_wave_center(wv, frame=f, x=px, y=py)

        # Hold last position through the end of the shot
        last_px, last_py = pts[-1]
        keyframe_wave_center(wv, frame=1, x=start_xy[0], y=start_xy[1])
        keyframe_wave_center(wv, frame=1 + Knobs.warmup_frames + Knobs.morph_frames, x=last_px, y=last_py)

        # Amplitude constant → decel_end, then fade out by last frame
        keyframe_wave_height(wv, frame=1, h=h)
        keyframe_wave_height(wv, frame=Knobs.decel_end, h=h)
        keyframe_wave_height(wv, frame=1 + Knobs.warmup_frames + Knobs.morph_frames, h=0.0)

        # Visual/brush sphere (constant size)
        sp = make_sphere(radius=Knobs.brush_radius, color=(0.2, 0.7, 1.0))
        sp.location = (sx, sy, Knobs.brush_altitude)
        keyframe_linear(sp, "location", 1)
        for f, (px, py) in zip(step_frames, pts):
            sp.location = (px, py, Knobs.brush_altitude)
            keyframe_linear(sp, "location", f)
        sp.location = (last_px, last_py, Knobs.brush_altitude)
        keyframe_linear(sp, "location", 1 + Knobs.warmup_frames + Knobs.morph_frames)

        if use_brush:
            add_dynamic_paint_brush(sp)

        col.objects.link(sp)
        for c in list(sp.users_collection):
            if c.name != col.name:
                c.objects.unlink(sp)
        spheres.append(sp)

    # Collective, long-wavelength wave (ramps up during the full morph window)
    collective = add_wave_modifier(
        plane,
        name="Wave-Collective",
        height=0.0,
        width=Knobs.collective_width,
        narrowness=Knobs.collective_narrowness,
        use_x=True,
        use_y=True,
    )
    keyframe_wave_height(collective, frame=Knobs.warmup_frames, h=0.0)
    keyframe_wave_height(collective, frame=1 + Knobs.warmup_frames + Knobs.morph_frames, h=Knobs.collective_height_final)

    return spheres, wavelets, collective


# ============================
# SECTION 7 — MAIN ENTRYPOINT
# ============================

def main(Knobs: Knobs) -> None:
    random.seed(Knobs.seed)
    nuke_scene()
    set_cycles(Knobs)

    plane = build_lattice(Knobs)
    dp_mod = add_dynamic_paint_canvas(plane) if Knobs.use_dynamic_paint else None

    add_camera(Knobs)
    add_lights()

    spheres, wavelets, collective = add_brush_spheres_and_wavelets(
        Knobs, plane, use_brush=Knobs.use_dynamic_paint
    )

    if dp_mod is not None and hasattr(dp_mod, "canvas_settings"):
        cvs = dp_mod.canvas_settings.canvas_surfaces.active
        for (attr, f1, v1), (_, f2, v2) in [
            (("wave_damping", Knobs.warmup_frames, 0.02), ("wave_damping", 1 + Knobs.warmup_frames + Knobs.morph_frames, 0.25)),
            (("timescale", Knobs.warmup_frames, 1.0), ("timescale", 1 + Knobs.warmup_frames + Knobs.morph_frames, 0.5)),
        ]:
            if hasattr(cvs, attr):
                setattr(cvs, attr, v1)
                keyframe_linear(cvs, attr, f1)
                setattr(cvs, attr, v2)
                keyframe_linear(cvs, attr, f2)

    bpy.context.scene.frame_set(1)
    print("[INFO] Scene built. Frames: 1–{}.".format(bpy.context.scene.frame_end))


if __name__ == "__main__":
    main(K)
