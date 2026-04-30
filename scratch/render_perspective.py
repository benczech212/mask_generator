import trimesh
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
import os
import argparse

def get_view_matrix(eye, target, up):
    fwd = target - eye
    fwd_len = np.linalg.norm(fwd)
    if fwd_len < 1e-6:
        fwd = np.array([0.0, 0.0, -1.0])
    else:
        fwd /= fwd_len
        
    right = np.cross(fwd, up)
    if np.linalg.norm(right) < 1e-6:
        # Collinear
        right = np.array([1.0, 0.0, 0.0])
    right /= np.linalg.norm(right)
    
    new_up = np.cross(right, fwd)
    
    view_matrix = np.eye(4)
    view_matrix[0, :3] = right
    view_matrix[1, :3] = new_up
    view_matrix[2, :3] = -fwd  # OpenGL convention: camera looks down -Z
    
    view_matrix[0, 3] = -np.dot(right, eye)
    view_matrix[1, 3] = -np.dot(new_up, eye)
    view_matrix[2, 3] = np.dot(fwd, eye)
    
    return view_matrix

def project_vertices(vertices, view_matrix, fov_y_degrees, aspect_ratio, near=1.0):
    # 1. Transform to camera space
    V = view_matrix
    verts_h = np.hstack((vertices, np.ones((len(vertices), 1))))
    verts_cam = (V @ verts_h.T).T
    
    # 2. Simple pinhole projection
    f = 1.0 / np.tan(np.radians(fov_y_degrees) / 2.0)
    
    # Z is negative in front of camera
    z = verts_cam[:, 2]
    # Small epsilon to avoid div by zero
    z_clamped = np.minimum(z, -1e-5)
    
    x_proj = (verts_cam[:, 0] * f / aspect_ratio) / (-z_clamped)
    y_proj = (verts_cam[:, 1] * f) / (-z_clamped)
    
    return np.column_stack((x_proj, y_proj)), z

def render_perspective(mesh, eye, target, up, output_path, width=1920, height=1080, fov_y=60.0):
    aspect_ratio = width / height
    
    view_matrix = get_view_matrix(eye, target, up)
    verts_2d, z_depths = project_vertices(mesh.vertices, view_matrix, fov_y, aspect_ratio)
    
    # Filter out faces that are behind the camera (z >= 0)
    # We check if all vertices of a face are behind the camera
    faces = mesh.faces
    face_z = z_depths[faces]
    valid_faces_mask = np.any(face_z < 0, axis=1)  # At least one vertex in front
    
    valid_faces = faces[valid_faces_mask]
    tris = verts_2d[valid_faces]
    
    # Backface culling (optional but helps performance and avoids inverted back faces)
    # For a silhouette, standard culling works:
    v0 = verts_2d[valid_faces[:, 0]]
    v1 = verts_2d[valid_faces[:, 1]]
    v2 = verts_2d[valid_faces[:, 2]]
    # Cross product 2D
    cross = (v1[:, 0] - v0[:, 0]) * (v2[:, 1] - v0[:, 1]) - (v1[:, 1] - v0[:, 1]) * (v2[:, 0] - v0[:, 0])
    # Clockwise or counter-clockwise depends on coord system, let's keep all for silhouette if we don't care,
    # or keep cross > 0
    front_facing = cross > 0
    tris = tris[front_facing]

    # Create figure
    dpi = 100
    fig = plt.figure(figsize=(width / dpi, height / dpi), dpi=dpi)
    fig.patch.set_facecolor('white')
    
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor('white')
    ax.axis('off')
    
    # Set limits based on standard NDC coordinates (-1 to 1) 
    # since we already applied aspect ratio in projection
    # Wait, our projection maps x and y to roughly [-1, 1].
    # Let's dynamically scale based on visible bounds to fit perfectly
    min_x, min_y = np.min(tris.reshape(-1, 2), axis=0)
    max_x, max_y = np.max(tris.reshape(-1, 2), axis=0)
    
    center_x = (min_x + max_x) / 2
    center_y = (min_y + max_y) / 2
    range_x = (max_x - min_x) * 1.05
    range_y = (max_y - min_y) * 1.05
    
    # We want to match the target aspect ratio of the image
    target_ratio = width / height
    actual_ratio = range_x / range_y if range_y != 0 else 1
    
    if actual_ratio < target_ratio:
        range_x = range_y * target_ratio
    else:
        range_y = range_x / target_ratio
        
    ax.set_xlim(center_x - range_x / 2, center_x + range_x / 2)
    ax.set_ylim(center_y - range_y / 2, center_y + range_y / 2)
    
    collection = PolyCollection(tris, facecolors='black', edgecolors='black', linewidths=0.1)
    ax.add_collection(collection)
    
    plt.savefig(output_path, dpi=dpi, transparent=False, facecolor='white')
    plt.close()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="Octagon Full.obj")
    parser.add_argument("--outdir", default="../renders")
    parser.add_argument("--list", action="store_true", help="List all bodies and their material groups, then exit")
    parser.add_argument("--hide-groups", type=str, default="", help="Comma separated list of material groups to hide")
    parser.add_argument("--hide-bodies", type=str, default="", help="Comma separated list of body names to hide")
    args = parser.parse_args()
    
    os.makedirs(args.outdir, exist_ok=True)
    
    mesh_path = args.input
    print(f"Loading {mesh_path}...")
    scene = trimesh.load(mesh_path, process=False)
    
    if isinstance(scene, trimesh.Trimesh):
        geometries = {'default': scene}
    else:
        geometries = scene.geometry
        
    # Group by material
    material_groups = {}
    for name, geom in geometries.items():
        mat_name = geom.visual.material.name if hasattr(geom.visual, 'material') and geom.visual.material else 'default'
        if mat_name not in material_groups:
            material_groups[mat_name] = []
        material_groups[mat_name].append((name, geom))
        
    if args.list:
        print("\n--- Geometry by Material Group ---")
        for mat_name, bodies in material_groups.items():
            print(f"Group: '{mat_name}' ({len(bodies)} bodies)")
            for b_name, _ in bodies:
                print(f"  - {b_name}")
        return

    hide_groups = [g.strip() for g in args.hide_groups.split(',') if g.strip()]
    hide_bodies = [b.strip() for b in args.hide_bodies.split(',') if b.strip()]
    
    # Collect visible meshes
    visible_meshes = []
    for mat_name, bodies in material_groups.items():
        if mat_name in hide_groups:
            print(f"Hiding group '{mat_name}'")
            continue
            
        for b_name, geom in bodies:
            if b_name in hide_bodies:
                print(f"Hiding body '{b_name}'")
                continue
            visible_meshes.append(geom)
            
    if not visible_meshes:
        print("No visible meshes left to render!")
        return
        
    # Combine visible meshes into one for rendering
    combined_mesh = trimesh.util.concatenate(visible_meshes)
    
    eye = np.array([6552.222, 15818.464, -3048.00])
    
    # Determine target: Center of mass
    target = combined_mesh.center_mass
    
    up = np.array([0.0, 0.0, 1.0])
    if abs(np.dot((target-eye)/np.linalg.norm(target-eye), up)) > 0.99:
        up = np.array([0.0, 1.0, 0.0]) # avoid collinearity
        
    out_file = os.path.join(args.outdir, "perspective_render.png")
    print(f"\nRendering {len(visible_meshes)} bodies from {eye} looking at {target} to {out_file}...")
    render_perspective(combined_mesh, eye, target, up, out_file)
    print("Done.")

if __name__ == "__main__":
    main()
