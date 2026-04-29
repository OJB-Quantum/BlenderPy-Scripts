'''
Authored by Onri Jay Benally (2025)
Open Access (CC-BY-4.0)
'''

import bpy
import numpy as np

# =============================================================================
# CONTROL KNOBS
# =============================================================================
# Adjust these physical and programmatic parameters to alter the simulation.

# Physical parameters governing the quantum wave packet
x0 = -20.0       # Initial spatial center of the wave packet
k0 = 5.0         # Central wavenumber dictating the initial propagation momentum
sigma = 1.0      # Initial spatial width (standard deviation)
m = 1.0          # Mass of the simulated quantum particle
hbar = 1.0       # Reduced Planck constant

# Animation timeline and temporal boundaries
tmin = 0.0       # Simulation start time
tmax = 12.0      # Simulation end time
frame_start = 1  # Blender timeline starting frame
frame_end = 400  # Blender timeline ending frame
num_frames = frame_end - frame_start + 1

# Spatial range and coordinate resolution
xmin = -20.0     # Minimum spatial boundary for numerical evaluation
xmax = 20.0      # Maximum spatial boundary for numerical evaluation
nx = 1200        # Number of discrete spatial evaluation points
x = np.linspace(xmin, xmax, nx)


# =============================================================================
# CORE WAVEFUNCTION COMPUTATION
# =============================================================================

def psi_free_particle(x, t, x0, k0, sigma, m=1.0, hbar=1.0):
    """
    Compute the one dimensional free particle Gaussian wave packet.
    
    This function calculates the complex probability amplitude over space
    and time. The computation incorporates the time dependent spreading 
    characteristic of dispersive quantum systems because the momentum 
    eigenstates propagate at varying phase velocities.
    """
    if t == 0:
        # Return the unperturbed initial state when time is strictly zero
        return np.exp(-0.5 * ((x - x0) / sigma)**2) * np.exp(1j * k0 * (x - x0))

    # Calculate the complex spreading factor
    alpha = 1.0 + 1j * (hbar * t) / (m * sigma**2)
    
    # Compute the time dependent normalization constant
    norm = 1.0 / np.sqrt(np.sqrt(np.pi) * sigma * alpha)

    # Determine the group velocity to translate the spatial coordinates
    vg = (hbar * k0) / m
    x_shift = x - x0 - vg * t

    # Assemble the complex exponent representing both the Gaussian envelope
    # and the propagating phase factor
    exponent = - (x_shift**2) / (2.0 * sigma**2 * alpha) + 1j * (k0 * x_shift / 2.0)
    
    return norm * np.exp(exponent)


# =============================================================================
# SCENE PREPARATION AND OBJECT GENERATION
# =============================================================================

# Purge all existing objects within the active scene to ensure a pristine state
for obj in bpy.context.scene.objects:
    bpy.data.objects.remove(obj, do_unlink=True)

# Instantiate a novel curve data block designated for the wave geometry
curve_data = bpy.data.curves.new("WaveCurve", type='CURVE')
curve_data.dimensions = '3D'
curve_data.bevel_depth = 0.01  # Apply a subtle cylindrical geometry to the curve

# Construct a polygonal spline to contain the discrete spatial coordinates
spline = curve_data.splines.new(type='POLY')
spline.points.add(nx - 1)  # Expand the point array to accommodate all spatial samples

# Generate the host object for the curve and link it to the master collection
wave_obj = bpy.data.objects.new("WavePacket", curve_data)
bpy.context.scene.collection.objects.link(wave_obj)


# =============================================================================
# TIMELINE ANIMATION HANDLER
# =============================================================================

def update_wave_curve(frame):
    """
    Recompute the wavefunction and update the spatial curve coordinates.
    
    This routine executes during each frame change event triggered by the 
    application timeline to ensure synchronous geometrical updates.
    """
    # Constrain the active frame integer to the defined temporal boundaries
    if frame < frame_start:
        frame = frame_start
    if frame > frame_end:
        frame = frame_end

    # Linearly interpolate the current time based on the active frame fraction
    frac = (frame - frame_start) / (num_frames - 1)
    t = tmin + frac * (tmax - tmin)

    # Evaluate the wavefunction and amplify the magnitude for enhanced visibility
    psi_vals = 5.0 * psi_free_particle(x, t, x0, k0, sigma, m=m, hbar=hbar)
    re_psi = np.real(psi_vals)
    im_psi = np.imag(psi_vals)

    # Iterate through the curve points to apply the calculated coordinates
    for i in range(nx):
        # The coordinate vector encapsulates the spatial position (x), 
        # the real amplitude (y), the imaginary amplitude (z), and weight (w)
        spline.points[i].co = (x[i], re_psi[i], im_psi[i], 1.0)


def frame_change_handler(scene):
    """
    Delegate the execution sequence to the curve update protocol.
    """
    # Verify the wave object persists in the scene before attempting modification
    if wave_obj.name in scene.objects:
        update_wave_curve(scene.frame_current)

# Purge existing pre-frame handlers and register the newly defined update protocol
bpy.app.handlers.frame_change_pre.clear()
bpy.app.handlers.frame_change_pre.append(frame_change_handler)


# =============================================================================
# EXECUTION INITIALIZATION
# =============================================================================

# Configure the global scene properties to align with the intended animation length
scene = bpy.context.scene
scene.frame_start = frame_start
scene.frame_end = frame_end

# Force an immediate evaluation at the initial frame to render the starting state
scene.frame_set(frame_start)

print("Simulation initialization successful. Initiate timeline playback to observe the temporal evolution.")
