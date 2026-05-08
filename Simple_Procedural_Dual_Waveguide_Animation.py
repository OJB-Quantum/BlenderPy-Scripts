"""PEP 8 and PEP 257 Compliant Procedural Waveguide Animation Generator.

This script initializes a dual bar photonic geometry and applies an animated emissive pulse
by directly engaging the internal Geometry Nodes interface.

Authored by Onri Jay Benally (2026)

Open Access (CC-BY-4.0)
"""

import subprocess
import sys

import bpy

# =============================================================================
# CONTROL KNOBS
# =============================================================================
BAR_LENGTH = 15.0
BAR_SPACING = 2.0
WAVEGUIDE_WIDTH = 0.4
WAVEGUIDE_HEIGHT = 0.2
PULSE_SPEED = 0.02
PULSE_WIDTH = 0.15
BLUR_ITERATIONS = 15
PULSE_COLOR = (0.0, 0.8, 1.0, 1.0)
EMISSION_STRENGTH = 50.0

subprocess.check_call([sys.executable, "-m", "pip", "install", "scipy", "numpy", "--quiet"])
# =============================================================================


def purge_existing_elements() -> None:
    """Removes existing meshes and curves to ensure a pristine computational environment."""
    for obj in bpy.data.objects:
        if obj.type in {'MESH', 'CURVE'}:
            bpy.data.objects.remove(obj, do_unlink=True)


def configure_hardware_acceleration() -> None:
    """Configures the primary rendering engine to utilize GPU compute capabilities."""
    bpy.context.scene.render.engine = 'CYCLES'
    
    try:
        prefs = bpy.context.preferences.addons['cycles'].preferences
        if hasattr(prefs, 'compute_device_type'):
            prefs.compute_device_type = 'CUDA'
            
        for device in prefs.devices:
            if device.type != 'CPU':
                device.use = True
                
        bpy.context.scene.cycles.device = 'GPU'
    except KeyError:
        pass


def generate_waveguide_material() -> bpy.types.Material:
    """Constructs the hybrid Glass and Emission material driven by a dynamically named attribute."""
    mat = bpy.data.materials.new(name="WaveguideMaterial")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    
    nodes.clear()
    
    node_output = nodes.new('ShaderNodeOutputMaterial')
    node_output.location = (400, 0)
    
    node_glass = nodes.new('ShaderNodeBsdfGlass')
    node_glass.location = (0, 100)
    
    node_emission = nodes.new('ShaderNodeEmission')
    node_emission.location = (0, -100)
    node_emission.inputs['Color'].default_value = PULSE_COLOR
    node_emission.inputs['Strength'].default_value = EMISSION_STRENGTH
    
    node_mix = nodes.new('ShaderNodeMixShader')
    node_mix.location = (200, 0)
    
    node_attr = nodes.new('ShaderNodeAttribute')
    node_attr.location = (0, 300)
    node_attr.attribute_name = 'PulseMask'
    
    links.new(node_attr.outputs['Fac'], node_mix.inputs[0])
    links.new(node_glass.outputs['BSDF'], node_mix.inputs[1])
    links.new(node_emission.outputs['Emission'], node_mix.inputs[2])
    links.new(node_mix.outputs['Shader'], node_output.inputs['Surface'])
    
    return mat


def construct_procedural_geometry(material: bpy.types.Material) -> None:
    """Generates the dual bar geometry and correctly routes the dynamic pulse attribute."""
    mesh_data = bpy.data.meshes.new("WaveguideMesh")
    obj = bpy.data.objects.new("DualWaveguide", mesh_data)
    bpy.context.collection.objects.link(obj)
    
    modifier = obj.modifiers.new(name="PhotonicNodes", type='NODES')
    tree = bpy.data.node_groups.new(name="WaveguideTree", type='GeometryNodeTree')
    modifier.node_group = tree
    
    nodes = tree.nodes
    links = tree.links
    
    node_line = nodes.new('GeometryNodeCurvePrimitiveLine')
    node_line.inputs['Start'].default_value = (0.0, 0.0, 0.0)
    node_line.inputs['End'].default_value = (BAR_LENGTH, 0.0, 0.0)
    
    node_transform = nodes.new('GeometryNodeTransform')
    node_transform.inputs['Translation'].default_value = (0.0, BAR_SPACING, 0.0)
    
    node_join = nodes.new('GeometryNodeJoinGeometry')
    
    node_resample = nodes.new('GeometryNodeResampleCurve')
    node_resample.inputs['Count'].default_value = 200
    
    node_profile = nodes.new('GeometryNodeCurvePrimitiveQuadrilateral')
    node_profile.inputs['Width'].default_value = WAVEGUIDE_WIDTH
    node_profile.inputs['Height'].default_value = WAVEGUIDE_HEIGHT
    
    node_curve_to_mesh = nodes.new('GeometryNodeCurveToMesh')
    
    node_spline_param = nodes.new('GeometryNodeSplineParameter')
    node_scene_time = nodes.new('GeometryNodeInputSceneTime')
    
    node_multiply = nodes.new('ShaderNodeMath')
    node_multiply.operation = 'MULTIPLY'
    node_multiply.inputs[1].default_value = PULSE_SPEED
    
    node_modulo = nodes.new('ShaderNodeMath')
    node_modulo.operation = 'MODULO'
    node_modulo.inputs[1].default_value = 1.0
    
    node_subtract = nodes.new('ShaderNodeMath')
    node_subtract.operation = 'SUBTRACT'
    
    node_abs = nodes.new('ShaderNodeMath')
    node_abs.operation = 'ABSOLUTE'
    
    node_compare = nodes.new('ShaderNodeMath')
    node_compare.operation = 'LESS_THAN'
    node_compare.inputs[1].default_value = PULSE_WIDTH
    
    node_blur = nodes.new('GeometryNodeBlurAttribute')
    node_blur.data_type = 'FLOAT'
    node_blur.inputs['Iterations'].default_value = BLUR_ITERATIONS
    
    node_store = nodes.new('GeometryNodeStoreNamedAttribute')
    node_store.data_type = 'FLOAT'
    node_store.domain = 'POINT'
    node_store.inputs['Name'].default_value = 'PulseMask'
    
    node_material = nodes.new('GeometryNodeSetMaterial')
    node_material.inputs['Material'].default_value = material
    
    node_output = nodes.new('NodeGroupOutput')
    tree.interface.new_socket(name="Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    
    links.new(node_line.outputs['Curve'], node_join.inputs[0])
    links.new(node_line.outputs['Curve'], node_transform.inputs['Geometry'])
    links.new(node_transform.outputs['Geometry'], node_join.inputs[0])
    
    links.new(node_join.outputs['Geometry'], node_resample.inputs['Curve'])
    links.new(node_resample.outputs['Curve'], node_store.inputs['Geometry'])
    links.new(node_store.outputs['Geometry'], node_curve_to_mesh.inputs['Curve'])
    links.new(node_profile.outputs['Curve'], node_curve_to_mesh.inputs['Profile Curve'])
    links.new(node_curve_to_mesh.outputs['Mesh'], node_material.inputs['Geometry'])
    links.new(node_material.outputs['Geometry'], node_output.inputs['Geometry'])
    
    links.new(node_scene_time.outputs['Frame'], node_multiply.inputs[0])
    links.new(node_multiply.outputs['Value'], node_modulo.inputs[0])
    
    links.new(node_spline_param.outputs['Factor'], node_subtract.inputs[0])
    links.new(node_modulo.outputs['Value'], node_subtract.inputs[1])
    
    links.new(node_subtract.outputs['Value'], node_abs.inputs[0])
    links.new(node_abs.outputs['Value'], node_compare.inputs[0])
    
    links.new(node_compare.outputs['Value'], node_blur.inputs['Value'])
    links.new(node_blur.outputs['Value'], node_store.inputs['Value'])


def main() -> None:
    """Coordinates the execution of the fully procedural geometric pipeline."""
    purge_existing_elements()
    configure_hardware_acceleration()
    waveguide_material = generate_waveguide_material()
    construct_procedural_geometry(waveguide_material)


if __name__ == "__main__":
    main()
