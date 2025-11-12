
"""
Blender animation: Wigner-function propagation on a 3-D surface mesh
with on-screen time HUD at bottom-right of the camera view.

Authored by Onri Jay Benally (2025)
Open Access (CC-BY-4.0)

Overview
--------
1) Solve a 1-D TDSE via a split-operator spectral method (ħ = m = 1).
2) Compute the Wigner map W(x, p, t) per frame (unitary FFT with norm="ortho").
3) Drive a quad-grid mesh: Z := z_scale * W; material color & emission follow Z.
4) Isometric orthographic camera (sensor width = 20), Cycles on GPU, starfield.
5) Time HUD: a camera-parented Text object that displays t per frame.

This version:
• 300 total frames (multi-n sweep: 64, 128, 256 with 100 frames each).
• Mesh resolution set to 288 × 288 (dense).
• Height exaggerated via z_scale (default 8.0 for visibility).
• Emission color matches the ramp; emission strength scales with |Z|.
• View Transform set to "Standard" to preserve ramp hues.
• Time HUD drawn at camera bottom-right; size from ortho view height.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Tuple

import bpy
import numpy as np


# ================================ Controls ===================================

@dataclass
class Knobs:
    """Top-level controls for physics, mesh, render, look, and HUD."""

    # ---- Physics grid & time (single-n mode) ----
    n: int = 128
    L: float = 12.0
    dt: float = 0.1

    # ---- Multi-n sweep (overrides 'n' and 'frames' if length >= 2) ----
    n_list: Tuple[int, ...] = (64, 128, 256)
    frames_per_n: int = 100  # 3 × 100 = 300 total frames

    # ---- Double-well V(x) = H * ((x/x0)^2 − 1)^2 ----
    barrier_height: float = 3.0
    separation: float = 4.0

    # ---- Initial Gaussian ψ(x, 0) ----
    x0: float = 2.0
    p0: float = -1.0
    sigma: float = 0.5

    # ---- Animation sampling (used only if single-n mode) ----
    frames: int = 300
    steps_per_frame: int = 4

    # ---- Wigner normalization (fixed across frames for stable colors) ----
    vmin: float = -0.2
    vmax: float = 0.4
    z_scale: float = 8.0  # exaggerated height

    # ---- Surface mesh resolution (downsample W to this) ----
    mesh_nx: int = 288
    mesh_ny: int = 288

    # ---- Render / look ----
    fps: int = 24
    use_optix_first: bool = True
    samples: int = 128
    sensor_size: float = 20.0
    world_star_scale: float = 2000.0
    world_star_thresh: float = 0.965
    star_strength: float = 1.0

    # ---- Material ----
    emission_strength: float = 2.0
    colormap: Tuple[
        Tuple[float, float, float],
        Tuple[float, float, float],
        Tuple[float, float, float],
    ] = (
        (0.231, 0.298, 0.753),  # blue
        (1.000, 1.000, 1.000),  # white
        (0.706, 0.016, 0.150),  # red
    )

    # ---- HUD (Time overlay) ----
    hud_margin_frac_x: float = 0.035   # fraction of view width from right edge
    hud_margin_frac_y: float = 0.040   # fraction of view height from bottom edge
    hud_height_frac: float = 0.045     # text height as fraction of view height
    hud_emission_strength: float = 3.0 # brighter than surface for readability
    hud_color: Tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0)


K = Knobs()


# ============================== Quantum System ===============================

class QuantumSystem:
    """1-D split-operator TDSE with Wigner transform (ħ=1, m=1)."""

    def __init__(self, n: int, L: float, dt: float) -> None:
        self.n = int(n)
        self.L = float(L)
        self.dt = float(dt)

        self.dx = self.L / self.n
        self.x = np.linspace(-self.L / 2.0, self.L / 2.0, self.n, endpoint=False)

        # momentum grid via FFT frequency; here p = k (ħ = m = 1)
        self.k = 2.0 * math.pi * np.fft.fftfreq(self.n, d=self.dx)

        self.psi = np.zeros(self.n, dtype=np.complex128)
        self.V = np.zeros(self.n, dtype=np.float64)
        self.U_V = np.ones(self.n, dtype=np.complex128)
        self.U_T = np.exp(-1j * (self.k ** 2) * self.dt / 2.0)

    def set_double_well(self, barrier_height: float, separation: float) -> None:
        x0 = separation / 2.0
        V = barrier_height * ((self.x / x0) ** 2 - 1.0) ** 2
        self.V = V.astype(np.float64, copy=False)
        self.U_V = np.exp(-1j * self.V * self.dt / 2.0)

    def set_initial_gaussian(self, x0: float, p0: float, sigma: float) -> None:
        norm = (1.0 / (2.0 * math.pi * sigma ** 2)) ** 0.25
        phase = np.exp(1j * p0 * self.x)
        envelope = np.exp(-((self.x - x0) ** 2) / (4.0 * sigma ** 2))
        self.psi = (norm * envelope * phase).astype(np.complex128, copy=False)

    def step(self) -> None:
        """Strang split: e^{-iV dt/2} FFT^{-1}[ e^{-i k^2 dt/2} FFT(...) ]."""
        self.psi *= self.U_V
        self.psi = np.fft.ifft(np.fft.fft(self.psi, norm="ortho") * self.U_T, norm="ortho")
        self.psi *= self.U_V

    def wigner(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Compute W(x, p) via an FFT over the relative coordinate y."""
        n = self.n
        y_idx = np.arange(-n // 2, n // 2)
        i_idx = np.arange(n)[:, None]
        plus = (i_idx + y_idx) % n
        minus = (i_idx - y_idx) % n
        g_xy = self.psi[plus] * np.conjugate(self.psi[minus])

        G = np.fft.fftshift(
            np.fft.fft(np.fft.fftshift(g_xy, axes=1), axis=1, norm="ortho"), axes=1
        )
        W = np.real(G) / math.pi

        nu = np.fft.fftfreq(n, d=self.dx)
        p = math.pi * np.fft.fftshift(nu)
        X, P = np.meshgrid(self.x, p)
        return X, P, W.T


# =========================== Precompute W frames ==============================

def precompute_single(cfg: Knobs) -> Tuple[np.ndarray, np.ndarray, List[np.ndarray]]:
    """Single-n precompute."""
    sys = QuantumSystem(cfg.n, cfg.L, cfg.dt)
    sys.set_double_well(cfg.barrier_height, cfg.separation)
    sys.set_initial_gaussian(cfg.x0, cfg.p0, cfg.sigma)

    X, P, W0 = sys.wigner()
    ix = np.linspace(0, cfg.n - 1, cfg.mesh_nx, dtype=int)
    iy = np.linspace(0, cfg.n - 1, cfg.mesh_ny, dtype=int)
    Xd = X[np.ix_(iy, ix)]
    Pd = P[np.ix_(iy, ix)]

    frames: List[np.ndarray] = [W0[np.ix_(iy, ix)]]
    for _ in range(1, cfg.frames):
        for _ in range(cfg.steps_per_frame):
            sys.step()
        _, _, Wn = sys.wigner()
        frames.append(Wn[np.ix_(iy, ix)])
    return Xd, Pd, frames


def precompute_multi(cfg: Knobs) -> Tuple[np.ndarray, np.ndarray, List[np.ndarray]]:
    """Multi-n precompute: concatenates segments for each n in n_list."""
    frames_all: List[np.ndarray] = []
    Xd0 = Pd0 = None

    for idx, n_i in enumerate(cfg.n_list):
        sys = QuantumSystem(n_i, cfg.L, cfg.dt)
        sys.set_double_well(cfg.barrier_height, cfg.separation)
        sys.set_initial_gaussian(cfg.x0, cfg.p0, cfg.sigma)

        X, P, W0 = sys.wigner()
        ix = np.linspace(0, n_i - 1, cfg.mesh_nx, dtype=int)
        iy = np.linspace(0, n_i - 1, cfg.mesh_ny, dtype=int)
        Xd_i = X[np.ix_(iy, ix)]
        Pd_i = P[np.ix_(iy, ix)]

        if idx == 0:
            Xd0, Pd0 = Xd_i, Pd_i  # mesh XY from first segment

        frames_all.append(W0[np.ix_(iy, ix)])
        for _ in range(1, cfg.frames_per_n):
            for _ in range(cfg.steps_per_frame):
                sys.step()
            _, _, Wn = sys.wigner()
            frames_all.append(Wn[np.ix_(iy, ix)])

        print(f"Prepared {cfg.frames_per_n} frames for n={n_i}.")

    assert Xd0 is not None and Pd0 is not None
    return Xd0, Pd0, frames_all


# ============================= Mesh + Material ================================

def create_grid_object(name: str, X: np.ndarray, Y: np.ndarray) -> bpy.types.Object:
    """Build a quad grid at (x, y, z=0). X, Y must be (ny, nx)."""
    ny, nx = X.shape
    verts = [(float(X[j, i]), float(Y[j, i]), 0.0) for j in range(ny) for i in range(nx)]
    faces = []
    for j in range(ny - 1):
        base = j * nx
        for i in range(nx - 1):
            v0 = base + i
            v1 = v0 + 1
            v2 = v0 + nx + 1
            v3 = v0 + nx
            faces.append((v0, v1, v2, v3))

    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.validate(clean_customdata=True)
    mesh.update()

    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def build_height_emission_material(
    name: str,
    z_min: float,
    z_max: float,
    colors: tuple[tuple[float, float, float],
                  tuple[float, float, float],
                  tuple[float, float, float]],
    emission_strength: float,
) -> bpy.types.Material:
    """
    Geometry(Position) → SeparateXYZ(Z)
      → MapRange(z_min..z_max → 0..1) ──────────► ColorRamp(blue/white/red) ─► Emission.Color
      → (ABS) → MapRange(0..max|z| → 0..1) → Multiply(emission_strength) ───► Emission.Strength
    """
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()

    # --- Nodes ---
    n_output = nodes.new("ShaderNodeOutputMaterial"); n_output.location = (900, 0)
    n_emis   = nodes.new("ShaderNodeEmission");       n_emis.location   = (720, 0)

    n_ramp   = nodes.new("ShaderNodeValToRGB");       n_ramp.location   = (480,  80)
    n_mapZ   = nodes.new("ShaderNodeMapRange");       n_mapZ.location   = (240,  80)   # for color
    n_abs    = nodes.new("ShaderNodeMath");           n_abs.location    = (240, -120); n_abs.operation = 'ABSOLUTE'
    n_mapA   = nodes.new("ShaderNodeMapRange");       n_mapA.location   = (480, -120)  # for strength
    n_mul    = nodes.new("ShaderNodeMath");           n_mul.location    = (640, -120); n_mul.operation = 'MULTIPLY'

    n_sep    = nodes.new("ShaderNodeSeparateXYZ");    n_sep.location    = ( 40,  0)
    n_geom   = nodes.new("ShaderNodeNewGeometry");    n_geom.location   = (-160, 0)

    # --- Map Z → [0,1] for the color ramp ---
    n_mapZ.inputs["From Min"].default_value = float(z_min)
    n_mapZ.inputs["From Max"].default_value = float(z_max)
    n_mapZ.inputs["To Min"].default_value   = 0.0
    n_mapZ.inputs["To Max"].default_value   = 1.0
    n_mapZ.clamp = True

    # --- Map |Z| → [0,1] for emission strength ---
    amp_max = max(abs(z_min), abs(z_max)) if max(abs(z_min), abs(z_max)) > 0 else 1.0
    n_mapA.inputs["From Min"].default_value = 0.0
    n_mapA.inputs["From Max"].default_value = float(amp_max)
    n_mapA.inputs["To Min"].default_value   = 0.0
    n_mapA.inputs["To Max"].default_value   = 1.0
    n_mapA.clamp = True

    # Multiply by user knob
    n_mul.inputs[1].default_value = float(emission_strength)

    # --- ColorRamp setup (safe edits: never delete the last stop) ---
    ramp = n_ramp.color_ramp
    while len(ramp.elements) > 2:
        ramp.elements.remove(ramp.elements[-1])
    while len(ramp.elements) < 2:
        ramp.elements.new(1.0)
    ramp.elements[0].position = 0.0
    ramp.elements[1].position = 1.0
    ramp.elements[0].color = (*colors[0], 1.0)  # blue end
    ramp.elements[1].color = (*colors[2], 1.0)  # red end
    mid = ramp.elements.new(0.5)                # mid = white
    mid.color = (*colors[1], 1.0)
    ramp.interpolation = 'LINEAR'

    # --- Wire it up ---
    links.new(n_geom.outputs["Position"], n_sep.inputs["Vector"])
    links.new(n_sep.outputs["Z"], n_mapZ.inputs["Value"])   # color path
    links.new(n_mapZ.outputs["Result"], n_ramp.inputs["Fac"])
    links.new(n_ramp.outputs["Color"], n_emis.inputs["Color"])

    links.new(n_sep.outputs["Z"], n_abs.inputs[0])          # strength path
    links.new(n_abs.outputs[0],   n_mapA.inputs["Value"])
    links.new(n_mapA.outputs["Result"], n_mul.inputs[0])
    links.new(n_mul.outputs[0],   n_emis.inputs["Strength"])

    links.new(n_emis.outputs["Emission"], n_output.inputs["Surface"])
    return mat


# ============================== World (stars) =================================

def make_star_world(scale: float, thresh: float, strength: float) -> None:
    """World: Voronoi → ColorRamp(threshold step) → Background on black."""
    world = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True

    nodes, links = world.node_tree.nodes, world.node_tree.links
    nodes.clear()

    n_out  = nodes.new("ShaderNodeOutputWorld");  n_out.location  = (600, 0)
    n_bg   = nodes.new("ShaderNodeBackground");   n_bg.location   = (400, 0)
    n_ramp = nodes.new("ShaderNodeValToRGB");     n_ramp.location = (180, 0)
    n_vor  = nodes.new("ShaderNodeTexVoronoi");   n_vor.location  = (-40, 0)

    n_vor.feature = 'F1'
    n_vor.distance = 'EUCLIDEAN'
    n_vor.inputs["Scale"].default_value = float(scale)
    n_vor.inputs["Randomness"].default_value = 1.0

    ramp = n_ramp.color_ramp
    while len(ramp.elements) > 2:
        ramp.elements.remove(ramp.elements[-1])
    while len(ramp.elements) < 2:
        ramp.elements.new(1.0)
    lo = max(0.0, min(1.0, thresh - 0.001))
    hi = max(0.0, min(1.0, thresh + 0.001))
    if hi <= lo:
        lo = max(0.0, thresh - 0.002)
        hi = min(1.0, thresh + 0.002)
    ramp.elements[0].position, ramp.elements[0].color = lo, (0.0, 0.0, 0.0, 1.0)
    ramp.elements[1].position, ramp.elements[1].color = hi, (1.0, 1.0, 1.0, 1.0)

    n_bg.inputs["Strength"].default_value = float(strength)

    links.new(n_vor.outputs["Distance"], n_ramp.inputs["Fac"])
    links.new(n_ramp.outputs["Color"], n_bg.inputs["Color"])
    links.new(n_bg.outputs["Background"], n_out.inputs["Surface"])


# =============================== Camera & Cycles ==============================

def setup_isometric_camera(sensor_size: float, target_obj: bpy.types.Object) -> bpy.types.Object:
    """Orthographic camera at ~54.7356° pitch and 45° yaw, framed to target."""
    cam_data = bpy.data.cameras.new("IsoCamera")
    cam = bpy.data.objects.new("IsoCamera", cam_data)
    bpy.context.collection.objects.link(cam)

    cam.data.type = 'ORTHO'
    cam.rotation_euler = (math.radians(54.7356), 0.0, math.radians(45.0))
    cam.location = (10.0, -10.0, 10.0)

    # Frame to object XY bounds (ortho_scale controls framing for ortho cams)
    bb = target_obj.bound_box
    minx, miny = min(v[0] for v in bb), min(v[1] for v in bb)
    maxx, maxy = max(v[0] for v in bb), max(v[1] for v in bb)
    diag_xy = math.hypot(maxx - minx, maxy - miny)
    cam.data.ortho_scale = 1.15 * diag_xy  # width in world units (orthographic)

    cam.data.sensor_width = float(sensor_size)  # documented property
    bpy.context.scene.camera = cam
    return cam


def enable_cycles_gpu(try_optix_first: bool, samples: int) -> None:
    """Switch to Cycles, enable GPU devices, set sample count."""
    scn = bpy.context.scene
    scn.render.engine = 'CYCLES'
    scn.cycles.samples = int(samples)
    scn.cycles.use_adaptive_sampling = True

    prefs = bpy.context.preferences
    if "cycles" not in prefs.addons:
        return
    cprefs = prefs.addons["cycles"].preferences

    backends = ["OPTIX", "CUDA", "HIP", "ONEAPI", "METAL"]
    if not try_optix_first:
        backends = ["CUDA", "OPTIX", "HIP", "ONEAPI", "METAL"]

    for b in backends:
        try:
            cprefs.compute_device_type = b
            cprefs.get_devices()
            for dev in cprefs.devices:
                dev.use = True
            scn.cycles.device = 'GPU'
            break
        except Exception:
            continue

    for sc in bpy.data.scenes:
        sc.cycles.device = 'GPU'


# ============================ Color Management ================================

def configure_view_settings(view: str = "Standard", look: str = "None",
                            exposure: float = 0.0, gamma: float = 1.0) -> None:
    """
    Set display transform so false-color ramps appear as authored.
    For scientific color maps, 'Standard' avoids filmic/AgX highlight roll-off.
    """
    vs = bpy.context.scene.view_settings
    vs.view_transform = view     # "Standard", "AgX", or "Filmic"
    vs.look = look
    vs.exposure = float(exposure)
    vs.gamma = float(gamma)


# ================================ HUD (Text) ==================================

def _ensure_emission_material(name: str,
                              color: Tuple[float, float, float, float],
                              strength: float) -> bpy.types.Material:
    """Create/reuse a simple Emission material for HUD text."""
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()
    n_out = nodes.new("ShaderNodeOutputMaterial"); n_out.location = (400, 0)
    n_em  = nodes.new("ShaderNodeEmission");       n_em.location  = (200, 0)
    n_em.inputs["Color"].default_value = color
    n_em.inputs["Strength"].default_value = float(strength)
    links.new(n_em.outputs["Emission"], n_out.inputs["Surface"])
    return mat


def create_hud_time_text(cam: bpy.types.Object,
                         text: str,
                         margin_frac_x: float,
                         margin_frac_y: float,
                         height_frac: float,
                         color: Tuple[float, float, float, float],
                         strength: float) -> bpy.types.Object:
    """
    Create a camera-parented Text (FONT) object at bottom-right of the camera view.

    Placement logic (orthographic):
        width  = cam.data.ortho_scale
        height = width * (res_y * pix_aspect_y) / (res_x * pix_aspect_x)
        local X right = +width/2 - margin_x ; local Y down = -height/2 + margin_y
        local Z = -1 puts text between camera and scene (inside clip start).
    """
    scn = bpy.context.scene
    ren = scn.render
    px_aspect = (ren.pixel_aspect_x, ren.pixel_aspect_y)
    width = cam.data.ortho_scale
    height = width * (ren.resolution_y * px_aspect[1]) / (ren.resolution_x * px_aspect[0])

    margin_x = width  * float(margin_frac_x)
    margin_y = height * float(margin_frac_y)
    text_h   = height * float(height_frac)

    # Create a FONT curve datablock and object
    font_curve = bpy.data.curves.new(name="HUD_Time_Curve", type='FONT')
    font_curve.body = text
    font_curve.size = text_h
    font_curve.align_x = 'RIGHT'
    if hasattr(font_curve, "align_y"):
        font_curve.align_y = 'BOTTOM'

    txt_obj = bpy.data.objects.new("HUD_Time", font_curve)

    # Parent to camera; position in camera local space
    txt_obj.parent = cam
    txt_obj.matrix_parent_inverse = cam.matrix_world.inverted()
    txt_obj.location = (width / 2.0 - margin_x, -height / 2.0 + margin_y, -1.0)
    txt_obj.rotation_euler = (0.0, 0.0, 0.0)

    # Emission material for crisp overlay
    hud_mat = _ensure_emission_material("HUD_Text_Emission", color, strength)
    if txt_obj.data.materials:
        txt_obj.data.materials[0] = hud_mat
    else:
        txt_obj.data.materials.append(hud_mat)

    # Link to scene
    bpy.context.collection.objects.link(txt_obj)
    return txt_obj


# ============================== Animation driver ==============================

class WignerAnimator:
    """Holds Wigner frames and updates mesh vertex Z + HUD time per frame."""

    def __init__(self,
                 obj: bpy.types.Object,
                 frames: List[np.ndarray],
                 z_scale: float,
                 dt_frame: float,
                 hud_obj: bpy.types.Object | None = None):
        self.obj = obj
        self.frames = frames
        self.z_scale = float(z_scale)
        self.dt_frame = float(dt_frame)
        self.hud_obj = hud_obj

        self.ny, self.nx = frames[0].shape
        self.vert_count = self.nx * self.ny
        self._co_buffer: np.ndarray | None = None

    def apply_frame(self, fidx: int) -> None:
        """Set vertex Z from frames[fidx] using foreach_get/foreach_set."""
        fidx = int(max(0, min(len(self.frames) - 1, fidx)))
        z = (self.z_scale * self.frames[fidx]).astype(np.float32).ravel()

        me = self.obj.data
        vcount = len(me.vertices)
        if vcount != self.vert_count:
            raise ValueError(
                f"Vertex count mismatch: mesh has {vcount}, expected {self.vert_count} "
                f"(nx={self.nx}, ny={self.ny})."
            )

        if self._co_buffer is None or self._co_buffer.size != 3 * vcount:
            self._co_buffer = np.empty(3 * vcount, dtype=np.float32)
            me.vertices.foreach_get("co", self._co_buffer)

        self._co_buffer[2::3] = z
        me.vertices.foreach_set("co", self._co_buffer)
        me.update()

    def update_hud_time(self, fidx: int) -> None:
        """Update HUD text to show simulation time t = fidx * dt_frame."""
        if self.hud_obj and hasattr(self.hud_obj.data, "body"):
            t = fidx * self.dt_frame
            self.hud_obj.data.body = f"t = {t:.3f} (arb. units)"

    def install(self, frame_start: int) -> None:
        """Register a frame_change_post handler for this animator (instance method)."""
        # Remove any prior handlers from earlier runs
        for h in list(bpy.app.handlers.frame_change_post):
            if getattr(h, "_is_wigner_handler", False):
                bpy.app.handlers.frame_change_post.remove(h)

        def _handler(scene):
            _ = scene
            f = bpy.context.scene.frame_current
            idx = max(0, f - frame_start)
            self.apply_frame(idx)
            self.update_hud_time(idx)

        _handler._is_wigner_handler = True  # tag for safe removal
        bpy.app.handlers.frame_change_post.append(_handler)


# ================================ Orchestration ===============================

def main(cfg: Knobs) -> None:
    # Choose single-n or multi-n path
    use_multi = cfg.n_list and len(cfg.n_list) >= 2

    if use_multi:
        Xd, Pd, frames = precompute_multi(cfg)
        total_frames = len(frames)
    else:
        Xd, Pd, frames = precompute_single(cfg)
        total_frames = len(frames)

    # Mesh & material
    surf = create_grid_object("WignerSurface", Xd, Pd)

    z_min = cfg.z_scale * cfg.vmin
    z_max = cfg.z_scale * cfg.vmax
    mat = build_height_emission_material(
        "WignerHeightEmission",
        z_min=z_min,
        z_max=z_max,
        colors=cfg.colormap,
        emission_strength=cfg.emission_strength,
    )
    surf.data.materials.clear()
    surf.data.materials.append(mat)

    # World, GPU, camera
    make_star_world(cfg.world_star_scale, cfg.world_star_thresh, cfg.star_strength)
    enable_cycles_gpu(cfg.use_optix_first, cfg.samples)

    # View transform for literal ramp display
    configure_view_settings(view="Standard", look="None", exposure=0.0, gamma=1.0)

    # Camera (must exist before HUD so we can size & place text)
    cam = setup_isometric_camera(cfg.sensor_size, surf)

    # HUD text (bottom-right), initial label at t = 0
    hud = create_hud_time_text(
        cam=cam,
        text="t = 0.000 (arb. units)",
        margin_frac_x=cg.hud_margin_frac_x if (cg := cfg) else 0.035,
        margin_frac_y=cfg.hud_margin_frac_y,
        height_frac=cfg.hud_height_frac,
        color=cfg.hud_color,
        strength=cfg.hud_emission_strength,
    )

    # Animator hookup (dt per frame = steps_per_frame * dt)
    dt_frame = cfg.dt * cfg.steps_per_frame
    anim = WignerAnimator(surf, frames, cfg.z_scale, dt_frame, hud_obj=hud)
    anim.apply_frame(0)
    anim.update_hud_time(0)
    anim.install(frame_start=1)

    # Timeline
    scn = bpy.context.scene
    scn.frame_start = 1
    scn.frame_end = total_frames
    scn.render.fps = cfg.fps

    # Aesthetics
    try:
        bpy.ops.object.select_all(action='DESELECT')
        surf.select_set(True)
        bpy.context.view_layer.objects.active = surf
        bpy.ops.object.shade_smooth()
    except Exception:
        pass

    mode = f"multi-n ({cfg.n_list}, {total_frames} frames)" if use_multi else f"single-n (n={cfg.n})"
    print(f"Wigner animation ready [{mode}]. Press Play.")
    print(f"Mesh: {cfg.mesh_nx}×{cfg.mesh_ny} | Steps/frame: {cfg.steps_per_frame} | z_scale: {cfg.z_scale}")
    print(f"HUD time dt_per_frame = {dt_frame:g} (arb. units) — bottom-right of camera view.")


if __name__ == "__main__":
    main(K)
