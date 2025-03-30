import bpy
import math

# --- PARAMETERS ---
num_points = 1000          # Number of points
theta_max = 20.0 * math.pi # Maximum angle (5 full turns)
x_max = 80.0               # Extend the spiral length on the x-axis to 10

# Blackman-Harris coefficients
a0 = 0.35875
a1 = 0.48829
a2 = 0.14128
a3 = 0.01168

# --- CREATE CURVE DATA ---
curve_data = bpy.data.curves.new(name="BHSpiralCurve", type='CURVE')
curve_data.dimensions = '3D'
curve_data.bevel_depth = 0.02  # curve thickness
curve_data.bevel_resolution = 4

# Create a POLY spline and add (num_points) points
spline = curve_data.splines.new(type='POLY')
spline.points.add(num_points - 1)

# --- GENERATE SPIRAL POINTS ---
for i in range(num_points):
    # Fraction from 0 to 1
    t = i / (num_points - 1)  
    # Theta and x values
    theta = t * theta_max
    x = t * x_max
    
    # Blackman-Harris window value
    # w[n] = a0 - a1*cos(2πn/(N-1)) + a2*cos(4πn/(N-1)) - a3*cos(6πn/(N-1))
    term = 2.0 * math.pi * i / (num_points - 1)
    window = (a0 
              - a1 * math.cos(term) 
              + a2 * math.cos(2.0 * term) 
              - a3 * math.cos(3.0 * term))
    
    # Radius (r = theta, modulated by Blackman-Harris window)
    r = theta * window
    
    # Convert to (x, y, z), with y & z "rotated"
    y = r * math.sin(theta)
    z = r * math.cos(theta)
    
    # Assign the coordinate; the 4th element is weight (for NURBS), keep 1 for POLY
    spline.points[i].co = (x, y, z, 1.0)

# --- CREATE AN OBJECT USING THIS CURVE ---
spiral_obj = bpy.data.objects.new("BHSpiralObject", curve_data)

# --- LINK OBJECT TO SCENE ---
collection = bpy.context.scene.collection
collection.objects.link(spiral_obj)

# Optionally select it and make active
bpy.context.view_layer.objects.active = spiral_obj
spiral_obj.select_set(True)

print("Blackman-Harris modulated spiral created (extended to 10 units) with a bevel depth of 0.02.")
