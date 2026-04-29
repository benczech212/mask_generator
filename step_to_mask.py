import argparse
import sys
import os
import gmsh
import trimesh
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from PIL import Image, ImageOps

def parse_args():
    parser = argparse.ArgumentParser(description="Convert STEP to silhouette PNG")
    parser.add_argument("input", help="Path to STEP file")
    parser.add_argument("--axis", choices=['x', '-x', 'y', '-y', 'z', '-z', 'all'], default='all',
                        help="The axis the camera is looking DOWN. Default is 'all' which generates 6 images.")
    parser.add_argument("--width", type=int, default=1920, help="Width of output mask (pixels)")
    parser.add_argument("--height", type=int, default=1080, help="Height of output mask (pixels)")
    parser.add_argument("--split-depths", action="store_true", help="Split faces facing the camera by depth into separate exports")
    return parser.parse_args()

def step_to_stl(step_path, stl_path):
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.merge(step_path)
        # 2D surface mesh is enough for silhouette
        gmsh.model.mesh.generate(2)
        gmsh.write(stl_path)
    finally:
        gmsh.finalize()

def render_mesh(mesh, axis, output_path, width=1920, height=1080, valid_faces=None):
    m = mesh.copy()
    
    # Project based on the specified view direction
    # The axis specifies which direction the "camera" is looking from (relative to the object).
    # We will grab the 2 perpendicular dimensions for the 2D projection.
    
    if axis == 'x':
        # Looking from +X towards origin.
        # Right direction = -Y, Up direction = Z
        verts_2d = m.vertices[:, [1, 2]]
        verts_2d[:, 0] = -verts_2d[:, 0]  # flip Y to be -Y
    elif axis == '-x':
        # Looking from -X towards origin.
        # Right direction = Y, Up direction = Z
        verts_2d = m.vertices[:, [1, 2]]
    elif axis == 'y':
        # Looking from +Y towards origin.
        # Right direction = X, Up direction = Z
        verts_2d = m.vertices[:, [0, 2]]
    elif axis == '-y':
        # Looking from -Y towards origin.
        # Right direction = -X, Up direction = Z
        verts_2d = m.vertices[:, [0, 2]]
        verts_2d[:, 0] = -verts_2d[:, 0]
    elif axis == 'z':
        # Looking from +Z towards origin.
        # Right direction = X, Up direction = Y
        verts_2d = m.vertices[:, [0, 1]]
    elif axis == '-z':
        # Looking from -Z towards origin.
        # Right direction = X, Up direction = -Y
        verts_2d = m.vertices[:, [0, 1]]
        verts_2d[:, 1] = -verts_2d[:, 1]
    
    if valid_faces is not None:
        tris = verts_2d[m.faces[valid_faces]]
    else:
        tris = verts_2d[m.faces]
    
    # Create fixed size figure
    dpi = 100
    fig = plt.figure(figsize=(width / dpi, height / dpi), dpi=dpi)
    fig.patch.set_facecolor('white')
    
    # Add axes spanning the whole image
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor('white')
    ax.axis('off')
    
    # Calculate bounds while perfectly matching aspect ratio
    min_x, min_y = np.min(verts_2d, axis=0)
    max_x, max_y = np.max(verts_2d, axis=0)
    center_x = (min_x + max_x) / 2
    center_y = (min_y + max_y) / 2
    range_x = (max_x - min_x) * 1.05  # Add a 5% margin
    range_y = (max_y - min_y) * 1.05
    
    target_ratio = width / height
    actual_ratio = range_x / range_y if range_y != 0 else 1
    
    if actual_ratio < target_ratio:
        # Height is the bottleneck, widen the X limit
        range_x = range_y * target_ratio
    else:
        # Width is the bottleneck, heighten the Y limit
        range_y = range_x / target_ratio
        
    ax.set_xlim(center_x - range_x / 2, center_x + range_x / 2)
    ax.set_ylim(center_y - range_y / 2, center_y + range_y / 2)
    
    # Fill faces with black
    collection = PolyCollection(tris, facecolors='black', edgecolors='black', linewidths=0.1)
    ax.add_collection(collection)
    
    # Save exact resolution
    plt.savefig(output_path, dpi=dpi, transparent=False, facecolor='white')
    plt.close()
    
    # Generate an inverted duplicate
    img = Image.open(output_path).convert('RGB')
    inverted_img = ImageOps.invert(img)
    base, ext = os.path.splitext(output_path)
    inverted_img.save(f"{base}_inverted{ext}")

def main():
    args = parse_args()
    if not os.path.exists(args.input):
        print(f"File not found: {args.input}")
        sys.exit(1)
        
    base_name = os.path.splitext(os.path.basename(args.input))[0]
    stl_path = f"temp_{base_name}.stl"
    
    print(f"Loading {args.input} via gmsh to {stl_path}...")
    step_to_stl(args.input, stl_path)
    
    print("Loading mesh via trimesh...")
    mesh = trimesh.load(stl_path)
    
    axes_to_render = ['x', '-x', 'y', '-y', 'z', '-z'] if args.axis == 'all' else [args.axis]
    
    print(f"Extents of model: {mesh.extents}")
    print(f"Center point: {mesh.center_mass}")
    
    for ax in axes_to_render:
        if args.split_depths:
            # First, render the whole image as requested
            out_path_whole = f"{base_name}_mask_{ax.replace('-', 'neg_')}_whole.png"
            print(f"Rendering axis {ax} whole to {out_path_whole}...")
            render_mesh(mesh, ax, out_path_whole, args.width, args.height)
            
            normal_map = {'x': [1,0,0], '-x': [-1,0,0], 'y': [0,1,0], '-y': [0,-1,0], 'z': [0,0,1], '-z': [0,0,-1]}
            target_normal = normal_map[ax]
            idx_map = {'x': 0, '-x': 0, 'y': 1, '-y': 1, 'z': 2, '-z': 2}
            axis_idx = idx_map[ax]
            
            dots = np.dot(mesh.face_normals, target_normal)
            facing_camera = np.where(dots > 0.99)[0]
            
            if len(facing_camera) == 0:
                print(f"No faces pointing to {ax}. Skipping.")
                continue
                
            depths = np.round(mesh.triangles_center[facing_camera, axis_idx], 2)
            unique_depths = np.unique(depths)
            
            print(f"Axis {ax}: Found {len(unique_depths)} unique depth layers.")
            for d in unique_depths:
                layer_faces = facing_camera[depths == d]
                out_path = f"{base_name}_mask_{ax.replace('-', 'neg_')}_depth_{d}.png"
                print(f"Rendering axis {ax} depth {d} to {out_path}...")
                render_mesh(mesh, ax, out_path, args.width, args.height, valid_faces=layer_faces)
        else:
            out_path = f"{base_name}_mask_{ax.replace('-', 'neg_')}.png"
            print(f"Rendering axis {ax} to {out_path}...")
            render_mesh(mesh, ax, out_path, args.width, args.height)
        
    if os.path.exists(stl_path):
        os.remove(stl_path)
        
    print("Done.")

if __name__ == "__main__":
    main()
