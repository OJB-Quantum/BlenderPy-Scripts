"""PEP 8 and PEP 257 compliant procedural waveguide animation generator.

This script initializes a dual bar photonic geometry and applies an animated
emissive pulse through Blender Geometry Nodes. The pulse system supports a
single pulse mode and a visible marching ant-trail mode.

Authored by Onri Jay Benally, 2026

Open Access, CC BY 4.0
"""

import bpy

# =============================================================================
# CONTROL KNOBS
# =============================================================================
BAR_LENGTH = 15.0
BAR_SPACING = 2.0
WAVEGUIDE_WIDTH = 0.4
WAVEGUIDE_HEIGHT = 0.2

RESAMPLE_COUNT = 1200

PULSE_SPEED = 0.04
PULSE_WIDTH = 0.05
BLUR_ITERATIONS = 15
PULSE_COLOR = (0.0, 0.8, 1.0, 1.0)
EMISSION_STRENGTH = 50.0

ANT_TRAIL_MODE = True

# Total pulse count in ant-trail mode, including the leading pulse.
ANT_TRAIL_COUNT = 16

# When enabled, spacing is computed as 1.0 / effective trail count.
# When disabled, ANT_TRAIL_SPACING is used directly.
ANT_TRAIL_AUTO_SPACING = True
ANT_TRAIL_SPACING = 0.06

# Count clamping prevents excessive overlap and poor sampling.
ANT_TRAIL_CLAMP_COUNT = True
ANT_TRAIL_MAX_COUNT = 64
ANT_TRAIL_MIN_SAMPLES_PER_PULSE = 24

# A duty cycle of 0.70 means each pulse may occupy at most 70 percent
# of its spacing cell after width and blur are considered together.
ANT_TRAIL_MAX_DUTY_CYCLE = 0.70

ANT_TRAIL_WIDTH = 0.008
ANT_TRAIL_DECAY = 1.0
ANT_TRAIL_BLUR_ITERATIONS = 8

ANT_TRAIL_AUTO_LIMIT_WIDTH = True
ANT_TRAIL_WIDTH_LIMIT_FACTOR = 0.35

ANT_TRAIL_AUTO_LIMIT_BLUR = True
# =============================================================================


def purge_existing_elements() -> None:
    """Remove existing meshes and curves for a clean procedural scene."""
    for obj in list(bpy.data.objects):
        if obj.type in {"MESH", "CURVE"}:
            bpy.data.objects.remove(obj, do_unlink=True)


def configure_hardware_acceleration() -> None:
    """Configure Cycles to use available GPU compute devices."""
    bpy.context.scene.render.engine = "CYCLES"

    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences

        if hasattr(prefs, "compute_device_type"):
            prefs.compute_device_type = "CUDA"

        for device in prefs.devices:
            if device.type != "CPU":
                device.use = True

        bpy.context.scene.cycles.device = "GPU"

    except (KeyError, TypeError, AttributeError):
        pass


def clamp_float(value: float, lower_bound: float, upper_bound: float) -> float:
    """Clamp a float to a closed interval."""
    return max(lower_bound, min(value, upper_bound))


def clamp_int(value: int, lower_bound: int, upper_bound: int) -> int:
    """Clamp an integer to a closed interval."""
    return max(lower_bound, min(int(value), upper_bound))


def generate_waveguide_material() -> bpy.types.Material:
    """Create a Glass and Emission material driven by PulseMask."""
    mat = bpy.data.materials.new(name="WaveguideMaterial")
    mat.use_nodes = True

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    node_output = nodes.new("ShaderNodeOutputMaterial")
    node_output.location = (400, 0)

    node_glass = nodes.new("ShaderNodeBsdfGlass")
    node_glass.location = (0, 100)

    node_emission = nodes.new("ShaderNodeEmission")
    node_emission.location = (0, -100)
    node_emission.inputs["Color"].default_value = PULSE_COLOR
    node_emission.inputs["Strength"].default_value = EMISSION_STRENGTH

    node_mix = nodes.new("ShaderNodeMixShader")
    node_mix.location = (200, 0)

    node_attr = nodes.new("ShaderNodeAttribute")
    node_attr.location = (0, 300)
    node_attr.attribute_name = "PulseMask"

    links.new(node_attr.outputs["Fac"], node_mix.inputs[0])
    links.new(node_glass.outputs["BSDF"], node_mix.inputs[1])
    links.new(node_emission.outputs["Emission"], node_mix.inputs[2])
    links.new(node_mix.outputs["Shader"], node_output.inputs["Surface"])

    return mat


def create_math_node(
    tree: bpy.types.NodeTree,
    operation: str,
    location: tuple[float, float] = (0.0, 0.0),
) -> bpy.types.Node:
    """Create a scalar math node with a selected operation."""
    node = tree.nodes.new("ShaderNodeMath")
    node.operation = operation
    node.location = location

    return node


def get_ant_trail_blur_padding(blur_iterations: int) -> float:
    """Estimate the normalized blur spread used for spacing safety checks."""
    safe_resample_count = max(1, int(RESAMPLE_COUNT))
    safe_blur_iterations = max(0, int(blur_iterations))

    return safe_blur_iterations / safe_resample_count


def get_requested_ant_trail_count() -> int:
    """Return the requested ant-trail pulse count after basic bounds."""
    safe_max_count = max(1, int(ANT_TRAIL_MAX_COUNT))
    requested_count = max(1, int(ANT_TRAIL_COUNT))

    return clamp_int(
        value=requested_count,
        lower_bound=1,
        upper_bound=safe_max_count,
    )


def get_sample_limited_ant_trail_count() -> int:
    """Return the largest pulse count allowed by the resampling density."""
    samples_per_pulse = max(1, int(ANT_TRAIL_MIN_SAMPLES_PER_PULSE))
    sample_limited_count = max(1, int(RESAMPLE_COUNT) // samples_per_pulse)

    return sample_limited_count


def get_width_limited_ant_trail_count(blur_iterations: int) -> int:
    """Return the largest count that satisfies the duty-cycle occupancy rule."""
    duty_cycle = clamp_float(
        value=ANT_TRAIL_MAX_DUTY_CYCLE,
        lower_bound=0.05,
        upper_bound=0.95,
    )
    requested_half_width = max(0.0, float(ANT_TRAIL_WIDTH))
    blur_padding = get_ant_trail_blur_padding(blur_iterations)
    effective_half_width = requested_half_width + blur_padding

    if effective_half_width <= 0.0:
        return max(1, int(ANT_TRAIL_MAX_COUNT))

    width_limited_count = int(duty_cycle / (2.0 * effective_half_width))

    return max(1, width_limited_count)


def get_effective_ant_trail_count(blur_iterations: int) -> int:
    """Return the ant-trail pulse count after count, sampling, and width limits."""
    pulse_count = get_requested_ant_trail_count()

    if ANT_TRAIL_CLAMP_COUNT:
        pulse_count = min(
            pulse_count,
            get_sample_limited_ant_trail_count(),
        )

        if ANT_TRAIL_AUTO_SPACING:
            pulse_count = min(
                pulse_count,
                get_width_limited_ant_trail_count(blur_iterations),
            )

    return max(1, pulse_count)


def get_effective_ant_trail_spacing(pulse_count: int) -> float:
    """Return normalized ant-trail spacing."""
    safe_pulse_count = max(1, int(pulse_count))

    if ANT_TRAIL_AUTO_SPACING:
        return 1.0 / safe_pulse_count

    return clamp_float(
        value=float(ANT_TRAIL_SPACING),
        lower_bound=1.0e-6,
        upper_bound=1.0,
    )


def get_domain_limited_ant_trail_count(
    pulse_count: int,
    spacing: float,
) -> int:
    """Clamp manual-spacing count so wrapped offsets avoid self-overlap."""
    if ANT_TRAIL_AUTO_SPACING:
        return max(1, int(pulse_count))

    safe_spacing = clamp_float(
        value=spacing,
        lower_bound=1.0e-6,
        upper_bound=1.0,
    )
    domain_limited_count = max(1, int(1.0 // safe_spacing))

    return min(max(1, int(pulse_count)), domain_limited_count)


def get_effective_ant_trail_width(
    spacing: float,
    blur_iterations: int,
) -> float:
    """Return an ant-trail half-width that preserves visible gaps."""
    requested_width = max(0.0, float(ANT_TRAIL_WIDTH))

    if ANT_TRAIL_AUTO_LIMIT_WIDTH:
        duty_cycle = clamp_float(
            value=ANT_TRAIL_MAX_DUTY_CYCLE,
            lower_bound=0.05,
            upper_bound=0.95,
        )
        blur_padding = get_ant_trail_blur_padding(blur_iterations)
        duty_limited_width = max(
            0.0,
            0.5 * duty_cycle * spacing - blur_padding,
        )
        factor_limited_width = max(
            0.0,
            ANT_TRAIL_WIDTH_LIMIT_FACTOR * spacing,
        )

        return min(
            requested_width,
            duty_limited_width,
            factor_limited_width,
        )

    return requested_width


def get_effective_ant_trail_blur_iterations(
    spacing: float,
    pulse_width: float,
) -> int:
    """Return ant-trail blur iterations after optional overlap control."""
    requested_blur_iterations = max(0, int(ANT_TRAIL_BLUR_ITERATIONS))

    if ANT_TRAIL_AUTO_LIMIT_BLUR:
        duty_cycle = clamp_float(
            value=ANT_TRAIL_MAX_DUTY_CYCLE,
            lower_bound=0.05,
            upper_bound=0.95,
        )
        available_blur_padding = max(
            0.0,
            0.5 * duty_cycle * spacing - pulse_width,
        )
        max_blur_iterations = int(available_blur_padding * max(1, RESAMPLE_COUNT))

        return min(requested_blur_iterations, max(0, max_blur_iterations))

    return requested_blur_iterations


def get_ant_trail_settings() -> tuple[int, float, float, int]:
    """Return count, spacing, half-width, and blur for ant-trail mode."""
    requested_blur_iterations = max(0, int(ANT_TRAIL_BLUR_ITERATIONS))

    pulse_count = get_effective_ant_trail_count(requested_blur_iterations)
    spacing = get_effective_ant_trail_spacing(pulse_count)

    pulse_count = get_domain_limited_ant_trail_count(
        pulse_count=pulse_count,
        spacing=spacing,
    )
    spacing = get_effective_ant_trail_spacing(pulse_count)

    pulse_width = get_effective_ant_trail_width(
        spacing=spacing,
        blur_iterations=requested_blur_iterations,
    )
    blur_iterations = get_effective_ant_trail_blur_iterations(
        spacing=spacing,
        pulse_width=pulse_width,
    )

    pulse_width = get_effective_ant_trail_width(
        spacing=spacing,
        blur_iterations=blur_iterations,
    )

    return pulse_count, spacing, pulse_width, blur_iterations


def create_shifted_phase(
    tree: bpy.types.NodeTree,
    base_phase_socket: bpy.types.NodeSocket,
    offset: float,
) -> bpy.types.NodeSocket:
    """Create a wrapped phase socket shifted behind the leading pulse."""
    links = tree.links
    normalized_offset = offset % 1.0

    node_add = create_math_node(tree, "ADD")
    node_add.inputs[1].default_value = 1.0 - normalized_offset

    node_modulo = create_math_node(tree, "MODULO")
    node_modulo.inputs[1].default_value = 1.0

    links.new(base_phase_socket, node_add.inputs[0])
    links.new(node_add.outputs["Value"], node_modulo.inputs[0])

    return node_modulo.outputs["Value"]


def create_wrapped_pulse_mask(
    tree: bpy.types.NodeTree,
    factor_socket: bpy.types.NodeSocket,
    phase_socket: bpy.types.NodeSocket,
    pulse_width: float,
) -> bpy.types.NodeSocket:
    """Create a periodic distance mask around a travelling pulse phase."""
    links = tree.links

    node_subtract = create_math_node(tree, "SUBTRACT")
    node_abs = create_math_node(tree, "ABSOLUTE")

    node_inverse = create_math_node(tree, "SUBTRACT")
    node_inverse.inputs[0].default_value = 1.0

    node_minimum = create_math_node(tree, "MINIMUM")

    node_compare = create_math_node(tree, "LESS_THAN")
    node_compare.inputs[1].default_value = pulse_width

    links.new(factor_socket, node_subtract.inputs[0])
    links.new(phase_socket, node_subtract.inputs[1])
    links.new(node_subtract.outputs["Value"], node_abs.inputs[0])
    links.new(node_abs.outputs["Value"], node_inverse.inputs[1])
    links.new(node_abs.outputs["Value"], node_minimum.inputs[0])
    links.new(node_inverse.outputs["Value"], node_minimum.inputs[1])
    links.new(node_minimum.outputs["Value"], node_compare.inputs[0])

    return node_compare.outputs["Value"]


def create_weighted_mask(
    tree: bpy.types.NodeTree,
    mask_socket: bpy.types.NodeSocket,
    weight: float,
) -> bpy.types.NodeSocket:
    """Scale a pulse mask by a segment brightness weight."""
    node_scale = create_math_node(tree, "MULTIPLY")
    node_scale.inputs[1].default_value = weight

    tree.links.new(mask_socket, node_scale.inputs[0])

    return node_scale.outputs["Value"]


def add_value_sockets(
    tree: bpy.types.NodeTree,
    value_sockets: list[bpy.types.NodeSocket],
) -> bpy.types.NodeSocket:
    """Add scalar sockets into one accumulated socket."""
    current_socket = value_sockets[0]

    for value_socket in value_sockets[1:]:
        node_add = create_math_node(tree, "ADD")
        tree.links.new(current_socket, node_add.inputs[0])
        tree.links.new(value_socket, node_add.inputs[1])
        current_socket = node_add.outputs["Value"]

    return current_socket


def create_clamped_mask(
    tree: bpy.types.NodeTree,
    value_socket: bpy.types.NodeSocket,
) -> bpy.types.NodeSocket:
    """Limit the accumulated pulse mask to the shader factor range."""
    node_minimum = create_math_node(tree, "MINIMUM")
    node_minimum.inputs[1].default_value = 1.0

    tree.links.new(value_socket, node_minimum.inputs[0])

    return node_minimum.outputs["Value"]


def create_ant_trail_mask(
    tree: bpy.types.NodeTree,
    factor_socket: bpy.types.NodeSocket,
    base_phase_socket: bpy.types.NodeSocket,
    pulse_count: int,
    spacing: float,
    pulse_width: float,
) -> bpy.types.NodeSocket:
    """Build the scalar pulse mask for single pulse or ant-trail mode."""
    weighted_masks = []

    for index in range(pulse_count):
        phase_socket = base_phase_socket

        if index > 0:
            phase_socket = create_shifted_phase(
                tree=tree,
                base_phase_socket=base_phase_socket,
                offset=index * spacing,
            )

        mask_socket = create_wrapped_pulse_mask(
            tree=tree,
            factor_socket=factor_socket,
            phase_socket=phase_socket,
            pulse_width=pulse_width,
        )

        weight = ANT_TRAIL_DECAY**index
        weighted_mask_socket = create_weighted_mask(
            tree=tree,
            mask_socket=mask_socket,
            weight=weight,
        )
        weighted_masks.append(weighted_mask_socket)

    combined_socket = add_value_sockets(
        tree=tree,
        value_sockets=weighted_masks,
    )

    return create_clamped_mask(
        tree=tree,
        value_socket=combined_socket,
    )


def create_single_pulse_mask(
    tree: bpy.types.NodeTree,
    factor_socket: bpy.types.NodeSocket,
    base_phase_socket: bpy.types.NodeSocket,
) -> bpy.types.NodeSocket:
    """Build the scalar pulse mask for single-pulse mode."""
    mask_socket = create_wrapped_pulse_mask(
        tree=tree,
        factor_socket=factor_socket,
        phase_socket=base_phase_socket,
        pulse_width=PULSE_WIDTH,
    )

    return create_clamped_mask(
        tree=tree,
        value_socket=mask_socket,
    )


def add_geometry_output_socket(tree: bpy.types.NodeTree) -> None:
    """Add a Geometry output socket with Blender 4.x and 3.x compatibility."""
    try:
        tree.interface.new_socket(
            name="Geometry",
            in_out="OUTPUT",
            socket_type="NodeSocketGeometry",
        )
    except AttributeError:
        tree.outputs.new("NodeSocketGeometry", "Geometry")


def construct_procedural_geometry(material: bpy.types.Material) -> None:
    """Generate dual bar geometry and route the dynamic pulse attribute."""
    mesh_data = bpy.data.meshes.new("WaveguideMesh")
    obj = bpy.data.objects.new("DualWaveguide", mesh_data)
    bpy.context.collection.objects.link(obj)

    modifier = obj.modifiers.new(name="PhotonicNodes", type="NODES")
    tree = bpy.data.node_groups.new(name="WaveguideTree", type="GeometryNodeTree")
    modifier.node_group = tree

    nodes = tree.nodes
    links = tree.links

    node_line = nodes.new("GeometryNodeCurvePrimitiveLine")
    node_line.inputs["Start"].default_value = (0.0, 0.0, 0.0)
    node_line.inputs["End"].default_value = (BAR_LENGTH, 0.0, 0.0)

    node_transform = nodes.new("GeometryNodeTransform")
    node_transform.inputs["Translation"].default_value = (
        0.0,
        BAR_SPACING,
        0.0,
    )

    node_join = nodes.new("GeometryNodeJoinGeometry")

    node_resample = nodes.new("GeometryNodeResampleCurve")
    node_resample.inputs["Count"].default_value = RESAMPLE_COUNT

    node_profile = nodes.new("GeometryNodeCurvePrimitiveQuadrilateral")
    node_profile.inputs["Width"].default_value = WAVEGUIDE_WIDTH
    node_profile.inputs["Height"].default_value = WAVEGUIDE_HEIGHT

    node_curve_to_mesh = nodes.new("GeometryNodeCurveToMesh")

    node_spline_param = nodes.new("GeometryNodeSplineParameter")
    node_scene_time = nodes.new("GeometryNodeInputSceneTime")

    node_multiply = create_math_node(tree, "MULTIPLY")
    node_multiply.inputs[1].default_value = PULSE_SPEED

    node_modulo = create_math_node(tree, "MODULO")
    node_modulo.inputs[1].default_value = 1.0

    if ANT_TRAIL_MODE:
        pulse_count, spacing, pulse_width, blur_iterations = get_ant_trail_settings()
    else:
        pulse_count = 1
        spacing = 1.0
        pulse_width = PULSE_WIDTH
        blur_iterations = BLUR_ITERATIONS

    node_blur = nodes.new("GeometryNodeBlurAttribute")
    node_blur.data_type = "FLOAT"
    node_blur.inputs["Iterations"].default_value = blur_iterations

    node_store = nodes.new("GeometryNodeStoreNamedAttribute")
    node_store.data_type = "FLOAT"
    node_store.domain = "POINT"
    node_store.inputs["Name"].default_value = "PulseMask"

    node_material = nodes.new("GeometryNodeSetMaterial")
    node_material.inputs["Material"].default_value = material

    node_output = nodes.new("NodeGroupOutput")
    add_geometry_output_socket(tree)

    links.new(node_line.outputs["Curve"], node_join.inputs[0])
    links.new(node_line.outputs["Curve"], node_transform.inputs["Geometry"])
    links.new(node_transform.outputs["Geometry"], node_join.inputs[0])

    links.new(node_join.outputs["Geometry"], node_resample.inputs["Curve"])

    links.new(node_scene_time.outputs["Frame"], node_multiply.inputs[0])
    links.new(node_multiply.outputs["Value"], node_modulo.inputs[0])

    if ANT_TRAIL_MODE:
        pulse_mask_socket = create_ant_trail_mask(
            tree=tree,
            factor_socket=node_spline_param.outputs["Factor"],
            base_phase_socket=node_modulo.outputs["Value"],
            pulse_count=pulse_count,
            spacing=spacing,
            pulse_width=pulse_width,
        )
    else:
        pulse_mask_socket = create_single_pulse_mask(
            tree=tree,
            factor_socket=node_spline_param.outputs["Factor"],
            base_phase_socket=node_modulo.outputs["Value"],
        )

    links.new(pulse_mask_socket, node_blur.inputs["Value"])
    links.new(node_blur.outputs["Value"], node_store.inputs["Value"])

    links.new(node_resample.outputs["Curve"], node_store.inputs["Geometry"])
    links.new(node_store.outputs["Geometry"], node_curve_to_mesh.inputs["Curve"])
    links.new(node_profile.outputs["Curve"], node_curve_to_mesh.inputs["Profile Curve"])
    links.new(node_curve_to_mesh.outputs["Mesh"], node_material.inputs["Geometry"])
    links.new(node_material.outputs["Geometry"], node_output.inputs["Geometry"])


def main() -> None:
    """Coordinate the procedural scene generation pipeline."""
    purge_existing_elements()
    configure_hardware_acceleration()
    waveguide_material = generate_waveguide_material()
    construct_procedural_geometry(waveguide_material)


if __name__ == "__main__":
    main()
