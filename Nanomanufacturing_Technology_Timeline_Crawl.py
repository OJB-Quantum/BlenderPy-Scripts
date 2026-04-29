"""
Star-Wars-style crawl for an ASCII tree for a Nanomanufacturing Technology Timeline, now using the Cycles engine,
and setting the crawl ("tree") to PURE BLUE with Emission Strength = 200.

Authored by Onri Jay Benally (2025)
Open Access (CC-BY-4.0)
"""

import bpy  # type: ignore
import math
import os
import random
from math import radians

# -----------------------------
# CONTROL KNOBS
# -----------------------------
# Render & output
RENDER_ENGINE = 'CYCLES'  # fixed per user request
FPS = 24
RENDER_RES_X = 1920
RENDER_RES_Y = 1080
OUTPUT_PATH = "/tmp/nanomanufacturing_crawl.mp4"
AUTORENDER = False  # set True to automatically render after scene build

# Cycles quality
CYCLES_SAMPLES = 30
PREVIEW_SAMPLES = 64
USE_DENOISE = True
CYCLES_CLAMP_DIRECT = 0.0
CYCLES_CLAMP_INDIRECT = 2.0
USE_LIGHT_TREE = True  # Cycles 3.4+
USE_GLARE = True       # compositor glow (Fog Glow) to emulate Bloom
GLARE_THRESHOLD = 6.0  # higher -> less glow
GLARE_SIZE = 4         # 4..9 reasonable; larger -> softer halo
GLARE_MIX = 0.0        # 0 = pure effect added; negative mixes original in

# Camera rig
CAMERA_FOCAL_MM = 36.0
CAMERA_LOC = (0.0, -10.0, 1.6)  # X, Y, Z
CAMERA_TARGET = (0.0, 0.0, 1.0)

# Timing (frames)
INTRO_FADE_IN = 2
INTRO_HOLD = 4
INTRO_FADE_OUT = 2
CRAWL_START_OFFSET = 1  # frames after intro ends
CRAWL_DURATION = 900

# Crawl geometry and motion
CRAWL_TILT_DEG = 31.0
CRAWL_DISTANCE_START = 4.0
CRAWL_DISTANCE_END = 120.0

# Text geometry
TEXT_SIZE = 0.35
LINE_SPACING = 1.00
EXTRUDE = 0.001  # 0.0 for purely flat glyphs

# Colors & emission
INTRO_BLUE = (0.450, 0.650, 1.000, 1.0)
CRAWL_COLOR_RGBA = (0.0, 0.0, 1.0, 1.0)  # PURE BLUE, per request
EMISSION_STRENGTH_INTRO = 5.0
EMISSION_STRENGTH_CRAWL = 200.0         # per request

# Star field
STAR_COUNT = 900
STAR_SIZE = 0.03
STAR_SPREAD_XY = 140.0  # half width of XY spread
STAR_SPREAD_Z = 80.0    # half height of Z spread
STAR_SEED = 42
STAR_EMISSION = 1.0

# Font discovery (set a known path if you have one)
MONO_FONT_CANDIDATES = [
    # Linux
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeMono.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansMono-Regular.ttf",
    "/usr/share/fonts/truetype/ubuntu/UbuntuMono-R.ttf",
    # macOS
    "/Library/Fonts/Courier New.ttf",
    "/System/Library/Fonts/Monaco.ttf",
    # Windows
    "C:\\Windows\\Fonts\\consola.ttf",          # Consolas
    "C:\\Windows\\Fonts\\cour.ttf",             # Courier New
    "C:\\Windows\\Fonts\\lucon.ttf",            # Lucida Console
]

# Intro line (Star-Wars-style)
INTRO_LINE = "A long time ago in a galaxy far, far away...."

# The full tree (exactly as provided)
TIMELINE_TEXT = r"""Timeline Towards Nanomanufacturing
├── BCE (Before Common Era)
│ ├── ~1,000,000 BCE: Control of Fire
│ ├── 6000–5500 BCE: Polished Obsidian Mirror
│ ├── ~5500 BCE: Mud Plug Irrigation
│ ├── ~4000 BCE: Early Optical Lenses
│ ├── ~4000–3500 BCE: Potter’s Wheel
│ ├── Late 4th mill. BCE: Tell Brak Eye Idols
│ ├── ~3500–3000 BCE: Wood/Stone Sluice Gate
│ ├── ~3500–3350 BCE: Pictorial Wheeled Wagon
│ ├── ~3200 BCE: Wooden Wheel + Axle
│ ├── 2600–2575 BCE: Rock-Crystal Inlaid Eyes
│ ├── 1600–1450 BCE: Minoan Rock-Crystal Lenses
│ ├── 1400–1200 BCE: Bronze-Age Workshop Lenses
│ ├── ~1070 BCE: Grass-Fibre Jar Stopper
│ ├── ~1000 BCE: Leather Flap Check-Valve
│ ├── 750–710 BCE: Nimrud/ Layard Lens
│ ├── ~6th C BCE: Discovery and early use of lodestone 
│ │    (Natural magnetite; compasses 4th–2nd C BCE)
│ ├── ~5th C BCE: Greek Theories of Optics
│ ├── 1st C BCE: Natural-Cork Stopper
│ └── 1st C BCE–1st C CE: Roman Bronze Plug-Valve
│ └── CE (Common Era)
├── 1st millennium CE →: Wood milling, water-powered sawmills
├── ~1st C CE: Transparent, colorless glass for optics 
│      (Roman decolorized glass)
├── ~1st C CE: Roman Magnifying Devices
├── 1st C CE: Roman Lead-Pipe Shut-Offs
├── 1021: Book of Optics
├── 13th C: Invention of Spectacles
├── 1570s CE: Wooden Barrel Bung
├── 1608: Invention of the Telescope
├── 1668: Reflecting Telescope
├── 1704: Newton's “Opticks”
├── 1717–1842: Photochemical Experimentation 
│      (Schulze, Scheele, Wedgwood & Davy, Herschel)
├── 1733: Achromatic Lens
├── 1762: Wheel-Blowing Cylinder
├── 1800: Infra-red Radiation
├── 1801: Ultra-violet Radiation
├── 1818–1820s: Metal milling machines (Whitney 1818)
├── 1820: Discovery of Electromagnetism
├── 1823: Invention of the Solenoid
├── 1829: Compound Air Compressor
├── 1832: DC Motor
├── 1837: Practical Electric Motor
├── 1842: Blueprinting (Cyanotype contact printing)
├── 1855: Mercury Displacement Pump
├── 1857: Geissler Tube
├── 1864: Maxwell's Equations
├── 1873: Theory of Photographic Process
├── ~1875: Crookes Tube
├── 1878: Early Screw Compressor Patent
├── 1879: Incandescent Light Bulb
├── 1882–1885: High-voltage transformers for AC networks
├── 1887: Photoelectric Effect (also listed under Electronics)
├── late-1880s: Single-phase AC induction motor
├── 1889: Three-phase AC induction motor
├── 1890: Branly Coherer
├── 1894: Lenard Window Tube (also listed under Electronics)
├── 1895: Perrin Cathode-Ray Charge
├── 1895: Perrin Charge-Collector
├── 1895: Lodge & Popov Coherer
├── 1897: Discovery of Electron
├── 1897: Cathode-Ray Tube (CRT)
├── 19–20th C: Industrial Plug/Gate/Check Valves
├── 1900: Planck's Quantum Theory
├── ~1901: Crystal Detector
├── 1902: Mercury Arc Rectifier
├── 1902–1903: Electron gun (thermionic/FEG; Wehnelt)
├── 1904: Carbon-Mic. Telephone Relay
├── 1904: Fleming Valve (Vacuum Diode)
├── 1904: Vacuum Tube (Thermionic)
├── 1905: Scroll Compressor Concept
├── 1905: Einstein Photoelectric Eq.
├── 1906: Triode Vacuum Tube
├── 1906: Mercury-Vapor Neg-Res Lamp
├── 1906: de Forest Audion (Triode)
├── 1913: Gaede Molecular Drag Pump
├── 1913: Vacuum-Tube Telephone Repeater
├── 1913 → 1929: Spinors
├── 1915: Diffusion Pump
├── 1920s: Radio-frequency vacuum-tube transceivers (two-way radio)
├── 1920s–1930s: CRT magnetic deflection yoke
├── 1923: Holweck Molecular Drag Pump
├── 1925: Field-Effect Transistor Concept
├── 1930s: Sintered permanent magnets (sintered Alnico)
├── 1931: Transmission Electron Microscopy (TEM)
├── 1934: Twin-Screw Compressor
├── 1934: Heil FET Patent
├── 1935: Modern Screw Compressor Patent
├── 1937: Scanning Electron Microscopy (SEM) concept
├── 1939: Convergent-Beam Electron Diffraction (CBED)
├── 1943: Electric Discharge Machining (EDM)
├── 1944: Siegbahn Molecular Drag Pump
├── 1947: Point-Contact Transistor
├── 1948: Bipolar Junction Transistor
├── 1950s: Electron-Beam Evaporation (PVD)
├── 1950s →: MEMS/ NEMS
├── 1951: Grown-Junction Transistor
├── 1952: Computer Numerical Control (NC)
├── 1953: MASERs
├── 1954: First Silicon Transistor
├── 1957: Sputter Ion Pump
├── 1958: Turbomolecular Pump
├── 1958: Waterjet (UHP)
├── 1959: Planar Process & MOSFET
├── Late 1950s: Integrated Circuits
├── 1960: LASERs
├── 1960: Gas LASERs (He–Ne)
├── 1960: First solid-state LASER (ruby)
├── 1960s →: Photonic Integrated Circuits (PICs; “integrated optics”)
├── 1960s: SEM scan/deflection coils
├── early 1960s: Contact Optical Lithography (1:1 shadow printing)
├── 1960s: E-beam deflection coils (vector scan)
├── 1960s: Chemical Vapor Deposition (CVD) microelectronics adoption
├── 1960s: Early SOI Concepts
├── 1960s: Thin-Film Displays
├── 1962: LEDs (visible)
├── 1962: Brushless DC motor (BLDC)
├── 1962: Thin-Film Transistors
├── 1963: CMOS Technology
├── 1963: Silicon-on-Sapphire
├── ~1965: Electron-Beam Lithography (EBL)
├── 1965–1967 →: LASER cutting (CO₂, gas-assist)
├── 1966: Optical fiber (concept)
├── 1967: Floating-Gate MOSFET
├── 1968: Metal-Organic CVD (MOCVD)
├── 1968–1970: Molecular Beam Epitaxy (MBE)
├── ~1969: Wire Electric Discharge Machining (WEDM)
├── late-1960s/1970s: Plasma-Enhanced CVD (PECVD)
├── 1970: Scanning Transmission Electron Microscopy (STEM)
├── 1970s: High-Resolution TEM (HRTEM)
├── 1970s: Cryopumps
├── 1970s: Precision Machining Scroll Prototypes
├── 1970s: Focused Ion Beam (FIB) Lithography/Milling
├── 1970s: Ion Beam Etching/Milling (IBE)
├── 1970s →: Microprocessors
├── 1970s: Computer Numerical Control (CNC)
├── 1972: X-ray Lithography
├── 1973: Scroll Nitrogen Compressor R&D
├── 1973: Projection Optical Lithography (Micralign)
├── 1973: Proximity Optical Lithography (gap “shadow” printing)
├── 1974: Magnetron Sputtering (planar high-rate)
├── 1974: Atomic Layer Deposition (ALD; “atomic layer epitaxy”)
├── mid-1970s: Reactive Ion Etching (RIE)
├── 1978: SPER SOI Process
├── 1980s: Optical-fiber fusion splicing (first commercial splicers)
├── Early 1980s: Commercial Scroll Compressors
├── 1980s: Screw Compressors in Korea
├── early 1980s: Deep-Ultraviolet (DUV) Lithography (KrF 248 nm)
├── 1980s →: LASER Lithography (direct-write & stepper)
├── 1980s–1990s: Micro-molding (micro-injection molding)
├── 1980s →: Micromachining (silicon bulk/surface)
├── 1980s: IBM SOI Research
├── 1980: High-Electron-Mobility Transistor (HEMT)
├── 1981/1983: Quantum dots (QDs)
├── 1982: Abrasive-waterjet cutting (AWJ)
├── 1984/1986: Resin 3D printing (SLA)
├── 1989: Fused Deposition Modeling (FDM) 3D printing (patent)
├── 1990s: Facing-Target Magnetron Sputtering (FTS) adoption
├── 1990s: Grayscale Lithography (dose-modulated 3D resist)
├── 1990s: Cryogenic Reactive Ion Etching (cryo-RIE)
├── 1990: Peregrine SOS Process
├── 1990s: FinFET Development
├── early 1990s: High-Density Plasma PECVD (HDP-CVD)
├── 1990s: Resin 3D printing (DLP)
├── 1992: Soitec Smart-Cut SOI
├── 1993: Blue LEDs (InGaN/GaN)
├── 1993: Oil-Free Scroll Air Compressors
├── 1993: Metal sinter 3D printing (binder-jet + sinter) concept
├── 1993: Quantum dots (manufacturable synthesis)
├── ~1994: Quantum-dot LASERs
├── 1995: GaN LASERs (violet/blue diodes)
├── 1995: Nanoimprint Lithography (NIL)
├── 1995: IBM Commercial SOI
├── 1997: Two-Photon Lithography/ Polymerization
├── Late 20th C: Metamaterials
├── late-1990s →: Nano-molding (polymer nano-replication)
├── late-1990s: Fiber-LASER cutting (concept)
├── 2000s: Thin-Film LASERs
├── 2000s →: GaN LASER Lithography (violet 405 nm diode)
├── 2000s: Thin-Film Lumped Elements
├── 2000s: Thin-Film Distributed Elements
├── 2000s: Thin-Film Filters
├── 2000s: Thin-Film Sensors
├── 2000s: Thin-Film Interfaces
├── 2001: RF-SOI
├── 2002: FD-SOI LSI
├── 2008–2010s →: Quantum Photonic Integrated Circuits (QPICs)
├── 2010s–2020s: Cryogenic Atomic Layer Deposition (cryo-ALD)
├── mid-2010s →: Atomic Layer Etching (ALE)
├── 2010s–2020s: Cryogenic Atomic Layer Etching (cryo-ALE)
├── 2010s →: GaN LASER Lithography, near-UV 375 nm
├── 2010s: Gate-All-Around FET
├── 2012: GlobalFoundries & ST FD-SOI
├── 2015: Samsung 28 FDS
├── 2016–2017: Metal fused deposition modeling 
│      (bound-metal extrusion + sinter)
├── 2017: FinFET-on-SOI
├── ~2019+: Extreme Ultraviolet (EUV) Lithography (13.5 nm; HVM)
├── 2020s: High NA EUV Lithography
├── 2020s: Nanosheet Transistors
├── 2020s: Quantum Integrated Circuits
├── 2020s: Thin-Film Amplifiers
├── 2020s: Thin-Film Energy Harvesters
├── 2020s: Thin-Film Solar Cells
├── 2020s: Quantum IC/ Chiplets/ Modules
└── 2021 →: LASER balancing (ablation) for turbomolecular rotors
"""

# -----------------------------
# UTILITIES
# -----------------------------
def clear_scene() -> None:
    """Remove all existing objects, meshes, materials, worlds."""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    # Purge data-blocks with zero users
    for datablock in (bpy.data.meshes, bpy.data.materials, bpy.data.textures,
                      bpy.data.images, bpy.data.cameras, bpy.data.lights, bpy.data.curves,
                      bpy.data.collections, bpy.data.worlds):
        for block in list(datablock):
            if block.users == 0:
                datablock.remove(block)


def setup_render_cycles() -> None:
    """Configure Cycles, compositor, and output settings."""
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.render.fps = FPS
    scene.render.resolution_x = RENDER_RES_X
    scene.render.resolution_y = RENDER_RES_Y
    scene.render.resolution_percentage = 100

    # Cycles settings
    cycles = scene.cycles
    cycles.samples = CYCLES_SAMPLES
    cycles.preview_samples = PREVIEW_SAMPLES
    cycles.use_adaptive_sampling = True
    cycles.use_light_tree = USE_LIGHT_TREE
    cycles.sample_clamp_direct = CYCLES_CLAMP_DIRECT
    cycles.sample_clamp_indirect = CYCLES_CLAMP_INDIRECT
    cycles.max_bounces = 8
    cycles.transparent_max_bounces = 8
    cycles.caustics_reflective = False
    cycles.caustics_refractive = False

    # Denoising (per-view-layer for recent Blender)
    try:
        bpy.context.view_layer.cycles.use_denoising = USE_DENOISE
    except Exception:
        pass

    # Output: FFmpeg/H.264
    scene.render.image_settings.file_format = 'FFMPEG'
    scene.render.ffmpeg.format = 'MPEG4'
    scene.render.ffmpeg.codec = 'H264'
    scene.render.ffmpeg.constant_rate_factor = 'HIGH'
    scene.render.ffmpeg.ffmpeg_preset = 'GOOD'
    scene.render.ffmpeg.gopsize = FPS * 2
    scene.render.ffmpeg.video_bitrate = 8000
    scene.render.filepath = OUTPUT_PATH

    # World: pure black
    if not bpy.data.worlds:
        world = bpy.data.worlds.new("World_Black")
    else:
        world = bpy.data.worlds[0]
    scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs['Color'].default_value = (0, 0, 0, 1)
    bg.inputs['Strength'].default_value = 1.0
    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(bg.outputs['Background'], out.inputs['Surface'])

    # Compositor: optional Fog Glow to emulate Bloom
    scene.use_nodes = True
    ntc = scene.node_tree
    ntc.nodes.clear()
    rl = ntc.nodes.new("CompositorNodeRLayers")
    comp = ntc.nodes.new("CompositorNodeComposite")
    viewer = ntc.nodes.new("CompositorNodeViewer")
    if USE_GLARE:
        glare = ntc.nodes.new("CompositorNodeGlare")
        glare.glare_type = 'FOG_GLOW'
        glare.mix = GLARE_MIX
        glare.threshold = GLARE_THRESHOLD
        glare.size = GLARE_SIZE
        ntc.links.new(rl.outputs['Image'], glare.inputs['Image'])
        ntc.links.new(glare.outputs['Image'], comp.inputs['Image'])
        ntc.links.new(glare.outputs['Image'], viewer.inputs['Image'])
    else:
        ntc.links.new(rl.outputs['Image'], comp.inputs['Image'])
        ntc.links.new(rl.outputs['Image'], viewer.inputs['Image'])


def find_monospaced_font() -> bpy.types.VectorFont:
    """Try to load a monospaced font; fallback to Blender's default."""
    for pth in MONO_FONT_CANDIDATES:
        if os.path.exists(pth):
            try:
                return bpy.data.fonts.load(pth)
            except Exception:
                pass
    return bpy.data.fonts.get("Bfont")


def make_fade_emission_material(name: str,
                                rgba: tuple[float, float, float, float],
                                strength: float) -> tuple[bpy.types.Material, bpy.types.Node]:
    """Create a material that can fade (Transparent↔Emission) via a 'Fade' Value node.
    Robust across Blender versions (Eevee/Cycles) and avoids missing attributes.
    """
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True

    # Enable alpha blending so the Transparent BSDF can actually fade.
    if hasattr(mat, "blend_method"):
        mat.blend_method = 'BLEND'

    # Some Blender versions expose one of these; both are safe to skip in Cycles.
    try:
        if hasattr(mat, "shadow_method"):
            mat.shadow_method = 'NONE'
        elif hasattr(mat, "shadow_mode"):
            mat.shadow_mode = 'NONE'
    except Exception:
        # Not critical for Cycles; the fade still works without this.
        pass

    nt = mat.node_tree
    nt.nodes.clear()

    out = nt.nodes.new("ShaderNodeOutputMaterial")
    mix = nt.nodes.new("ShaderNodeMixShader")
    trans = nt.nodes.new("ShaderNodeBsdfTransparent")
    emis = nt.nodes.new("ShaderNodeEmission")
    fade = nt.nodes.new("ShaderNodeValue")
    fade.name = "Fade"
    fade.label = "Fade (0=transparent, 1=opaque)"

    emis.inputs['Color'].default_value = rgba
    emis.inputs['Strength'].default_value = strength
    fade.outputs[0].default_value = 0.0  # start transparent

    nt.links.new(trans.outputs['BSDF'], mix.inputs[1])
    nt.links.new(emis.outputs['Emission'], mix.inputs[2])
    nt.links.new(mix.outputs['Shader'], out.inputs['Surface'])
    nt.links.new(fade.outputs[0], mix.inputs['Fac'])

    return mat, fade


def add_camera_and_target() -> tuple[bpy.types.Object, bpy.types.Object]:
    """Create a camera and an Empty target; set Track To constraint."""
    cam_data = bpy.data.cameras.new("Camera")
    cam_data.lens = CAMERA_FOCAL_MM
    cam = bpy.data.objects.new("Camera", cam_data)
    bpy.context.collection.objects.link(cam)
    cam.location = CAMERA_LOC

    target = bpy.data.objects.new("CamTarget", None)
    bpy.context.collection.objects.link(target)
    target.empty_display_type = 'PLAIN_AXES'
    target.location = CAMERA_TARGET

    c = cam.constraints.new(type='TRACK_TO')
    c.target = target
    c.track_axis = 'TRACK_NEGATIVE_Z'
    c.up_axis = 'UP_Y'
    return cam, target


def create_starfield(count: int,
                     size: float,
                     spread_xy: float,
                     spread_z: float,
                     seed: int,
                     emission_strength: float) -> None:
    """Create a star field via instanced emissive icospheres."""
    random.seed(seed)

    # Container mesh with many vertices
    mesh = bpy.data.meshes.new("StarsMesh")
    verts = []
    for _ in range(count):
        x = random.uniform(-spread_xy, spread_xy)
        y = random.uniform(0.0, spread_xy * 1.5)  # mostly in front of camera
        z = random.uniform(-spread_z, spread_z)
        verts.append((x, y, z))
    mesh.from_pydata(verts, [], [])
    stars = bpy.data.objects.new("Stars", mesh)
    bpy.context.collection.objects.link(stars)
    stars.instance_type = 'VERTS'

    # Prototype star (emissive icosphere)
    star_mat = bpy.data.materials.new("Star_Emission")
    star_mat.use_nodes = True
    nt = star_mat.node_tree
    nt.nodes.clear()
    emis = nt.nodes.new("ShaderNodeEmission")
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    emis.inputs['Color'].default_value = (1, 1, 1, 1)
    emis.inputs['Strength'].default_value = emission_strength
    nt.links.new(emis.outputs['Emission'], out.inputs['Surface'])

    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=size, location=(0, 0, 0))
    proto = bpy.context.object
    proto.name = "StarProto"
    proto.data.materials.append(star_mat)
    proto.parent = stars  # DupliVerts: child is instanced on parent vertices
    proto.hide_set(True)  # hide prototype (instances still render)


def create_text_object(name: str,
                       text: str,
                       font: bpy.types.VectorFont | None,
                       size: float,
                       line_spacing: float,
                       extrude: float,
                       align_x: str,
                       align_y: str,
                       material: bpy.types.Material) -> bpy.types.Object:
    """Create a curved text object with material and typographic settings."""
    curve = bpy.data.curves.new(name=name, type='FONT')
    curve.body = text
    if font:
        curve.font = font
    curve.size = size
    curve.space_line = line_spacing
    curve.extrude = extrude
    curve.align_x = align_x
    curve.align_y = align_y
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(material)
    return obj


def keyfade(value_node, keys):
    """Animate a Value node (or compatible) by keyframing its output socket."""
    # Prefer the first output socket (e.g., "Value") if we're given a Node.
    socket = value_node.outputs[0] if hasattr(value_node, "outputs") else value_node
    for frame, val in keys:
        socket.default_value = float(val)
        socket.keyframe_insert(data_path="default_value", frame=frame)


def keyloc(obj: bpy.types.Object, frame: int, loc: tuple[float, float, float]) -> None:
    """Insert a location keyframe."""
    obj.location = loc
    obj.keyframe_insert(data_path="location", frame=frame)


# -----------------------------
# MAIN BUILD
# -----------------------------
def main() -> None:
    """Build the entire scene and animation (Cycles + blue crawl @ 200)."""
    clear_scene()
    setup_render_cycles()

    # Camera rig
    cam, _ = add_camera_and_target()
    bpy.context.scene.camera = cam

    # Star field
    create_starfield(STAR_COUNT, STAR_SIZE, STAR_SPREAD_XY, STAR_SPREAD_Z, STAR_SEED, STAR_EMISSION)

    # Materials (intro and crawl), both fade-able
    intro_mat, intro_fader = make_fade_emission_material("Mat_Intro", INTRO_BLUE, EMISSION_STRENGTH_INTRO)
    # >>> Per request: PURE BLUE + emission 200 for the TREE (crawl)
    crawl_mat, crawl_fader = make_fade_emission_material("Mat_Crawl", CRAWL_COLOR_RGBA, EMISSION_STRENGTH_CRAWL)

    # Font selection
    mono_font = find_monospaced_font()

    # Intro card (centered)
    intro_obj = create_text_object(
        name="IntroCard",
        text=INTRO_LINE,
        font=mono_font,
        size=0.7,
        line_spacing=1.0,
        extrude=0.0,
        align_x='CENTER',
        align_y='CENTER',
        material=intro_mat,
    )
    intro_obj.location = (0.0, 1.5, 1.0)

    # Intro fade: in -> hold -> out
    f0 = 1
    f1 = f0 + INTRO_FADE_IN
    f2 = f1 + INTRO_HOLD
    f3 = f2 + INTRO_FADE_OUT
    keyfade(intro_fader, [(f0, 0.0), (f1, 1.0), (f2, 1.0), (f3, 0.0)])

    # Crawl (monospaced, left aligned), PURE BLUE @ 200
    crawl_obj = create_text_object(
        name="CrawlText",
        text=TIMELINE_TEXT,
        font=mono_font,
        size=TEXT_SIZE,
        line_spacing=LINE_SPACING,
        extrude=EXTRUDE,
        align_x='LEFT',
        align_y='TOP_BASELINE',
        material=crawl_mat,
    )
    crawl_obj.rotation_euler = (radians(CRAWL_TILT_DEG), 0.0, 0.0)

    # Starting frame for crawl
    crawl_start = f3 + CRAWL_START_OFFSET
    crawl_end = crawl_start + CRAWL_DURATION

    # Fade-in for crawl so it doesn't pop
    keyfade(crawl_fader, [(crawl_start - 6, 0.0), (crawl_start + 24, 1.0)])

    # Motion: push away from camera along +Y
    start_loc = (-8.0, CRAWL_DISTANCE_START, 0.6)  # X shift for left alignment
    end_loc = (-8.0, CRAWL_DISTANCE_END, 8.0)
    keyloc(crawl_obj, crawl_start, start_loc)
    keyloc(crawl_obj, crawl_end, end_loc)

    # Frame range
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = crawl_end + FPS * 2

    if AUTORENDER:
        bpy.ops.render.render(animation=True)


if __name__ == "__main__":
    main()
