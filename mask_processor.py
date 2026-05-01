import os
import trimesh
import numpy as np
import matplotlib
matplotlib.use('Agg') # Headless
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from PIL import Image, ImageOps
import io
import base64
import lxml.etree as ET
import random
import re
import math

def get_scene_hierarchy(filepath):
    scene = trimesh.load(filepath, process=False)
    
    if isinstance(scene, trimesh.Trimesh):
        return {"id": "world", "name": "world", "geom": "default", "children": []}
        
    def build_tree(node):
        geom_name = scene.graph[node][1] if node in scene.graph else None
        children = scene.graph.transforms.children.get(node, [])
        
        result = {
            "id": node,
            "name": node,
            "geom": geom_name,
            "children": []
        }
        
        for child in children:
            result["children"].append(build_tree(child))
            
        return result
        
    return build_tree('world')

def _get_geometry_nodes(scene, node_id, include_children=True):
    nodes = []
    
    def collect(node):
        if node in scene.graph and scene.graph[node][1] is not None:
            nodes.append((node, scene.graph[node][1]))
        if include_children:
            for child in scene.graph.transforms.children.get(node, []):
                collect(child)
                
    collect(node_id)
    return nodes

def load_mesh(filepath, hidden_groups=None, hidden_bodies=None, only_nodes=None, return_face_mapping=False):
    if hidden_groups is None: hidden_groups = []
    if hidden_bodies is None: hidden_bodies = []
    
    scene = trimesh.load(filepath, process=False)
        
    if isinstance(scene, trimesh.Trimesh):
        if return_face_mapping:
            return scene, {}, scene
        return scene
        
    if not scene.geometry:
        raise ValueError("No geometry found in the file.")
        
    visible_meshes = []
    face_mapping = {}
    current_face_count = 0
    
    # If only_nodes is specified, we collect all descendants of those nodes
    allowed_nodes = set()
    if only_nodes:
        def collect_allowed(node):
            allowed_nodes.add(node)
            for child in scene.graph.transforms.children.get(node, []):
                collect_allowed(child)
        for n in only_nodes:
            if n in scene.graph: collect_allowed(n)
            
    def traverse(node):
        nonlocal current_face_count
        if only_nodes and node not in allowed_nodes:
            # We don't skip children entirely here unless the node is hidden, 
            # because the requested node might be a child of this node.
            pass
        elif node in hidden_groups or node in hidden_bodies:
            return # Skip this node and all children
            
        geom_name = scene.graph[node][1] if node in scene.graph else None
        if geom_name is not None and geom_name in scene.geometry:
            if (not only_nodes) or (node in allowed_nodes):
                transform, _ = scene.graph.get(node)
                geom = scene.geometry[geom_name].copy()
                geom.apply_transform(transform)
                visible_meshes.append(geom)
                
                num_faces = len(geom.faces)
                mat_name = geom.visual.material.name if hasattr(geom.visual, 'material') and geom.visual.material else 'material_0'
                
                if node not in face_mapping:
                    face_mapping[node] = {}
                    
                # Create a mapping of face_idx -> facet_idx
                face_to_facet = {}
                if hasattr(geom, 'facets') and geom.facets:
                    for i, facet in enumerate(geom.facets):
                        for f in facet:
                            face_to_facet[f] = i
                            
                for f_idx in range(num_faces):
                    facet_idx = face_to_facet.get(f_idx, "curved")
                    layer_mat_name = f"{mat_name}_face_{facet_idx}"
                    
                    if layer_mat_name not in face_mapping[node]:
                        face_mapping[node][layer_mat_name] = []
                        
                    face_mapping[node][layer_mat_name].append(current_face_count + f_idx)
                    
                current_face_count += num_faces
            
        for child in scene.graph.transforms.children.get(node, []):
            traverse(child)
            
    traverse('world')
        
    if not visible_meshes:
        if return_face_mapping: return trimesh.Trimesh(), {}, scene
        return trimesh.Trimesh()
        
    full_mesh = trimesh.util.concatenate(visible_meshes)
    if return_face_mapping:
        return full_mesh, face_mapping, scene
    return full_mesh


normal_map = {
    'x': [1,0,0], '-x': [-1,0,0], 
    'y': [0,1,0], '-y': [0,-1,0], 
    'z': [0,0,1], '-z': [0,0,-1]
}

def cluster_depths(depths, threshold=0.005):
    if len(depths) == 0:
        return depths
        
    sorted_idx = np.argsort(depths)
    sorted_vals = depths[sorted_idx]
    
    new_depths = np.zeros_like(depths)
    current_cluster_start = 0
    
    for i in range(1, len(sorted_vals)):
        if sorted_vals[i] - sorted_vals[current_cluster_start] > threshold:
            avg = np.mean(sorted_vals[current_cluster_start:i])
            for j in range(current_cluster_start, i):
                new_depths[sorted_idx[j]] = avg
            current_cluster_start = i
            
    avg = np.mean(sorted_vals[current_cluster_start:])
    for j in range(current_cluster_start, len(sorted_vals)):
        new_depths[sorted_idx[j]] = avg
        
    return new_depths

def get_view_matrix(eye, target, up):
    fwd = target - eye
    fwd_len = np.linalg.norm(fwd)
    if fwd_len < 1e-6: fwd = np.array([0.0, 0.0, -1.0])
    else: fwd = fwd / fwd_len
        
    right = np.cross(fwd, up)
    if np.linalg.norm(right) < 1e-6: right = np.array([1.0, 0.0, 0.0])
    right = right / np.linalg.norm(right)
    
    new_up = np.cross(right, fwd)
    
    view_matrix = np.eye(4)
    view_matrix[0, :3] = right
    view_matrix[1, :3] = new_up
    view_matrix[2, :3] = -fwd  # OpenGL convention: down -Z
    
    view_matrix[0, 3] = -np.dot(right, eye)
    view_matrix[1, 3] = -np.dot(new_up, eye)
    view_matrix[2, 3] = np.dot(fwd, eye)
    return view_matrix

def project_perspective(vertices, view_matrix, fov_y_degrees, aspect_ratio):
    V = view_matrix
    verts_h = np.hstack((vertices, np.ones((len(vertices), 1))))
    verts_cam = (V @ verts_h.T).T
    
    f = 1.0 / np.tan(np.radians(fov_y_degrees) / 2.0)
    z = verts_cam[:, 2]
    z_clamped = np.minimum(z, -1e-5)
    
    x_proj = (verts_cam[:, 0] * f / aspect_ratio) / (-z_clamped)
    y_proj = (verts_cam[:, 1] * f) / (-z_clamped)
    
    return np.column_stack((x_proj, y_proj)), z

def project_orthographic(vertices, view_matrix):
    V = view_matrix
    verts_h = np.hstack((vertices, np.ones((len(vertices), 1))))
    verts_cam = (V @ verts_h.T).T
    
    x_proj = verts_cam[:, 0]
    y_proj = verts_cam[:, 1]
    z = verts_cam[:, 2]
    
    return np.column_stack((x_proj, y_proj)), z

def get_transform_params(mesh, axis, width, height, camera_settings=None):
    m = mesh.copy()
    if axis == 'perspective' and camera_settings:
        eye = np.array(camera_settings.get('eye', camera_settings.get('pos', [0,0,0])))
        target = np.array(camera_settings['target'])
        up = np.array([0.0, 0.0, 1.0])
        if abs(np.dot((target-eye)/np.linalg.norm(target-eye), up)) > 0.99:
            up = np.array([0.0, 1.0, 0.0])
        
        view_matrix = get_view_matrix(eye, target, up)
        aspect_ratio = width / height
        # Project using actual FOV
        fov = float(camera_settings.get('fov', 60.0))
        verts_2d, z_depths = project_perspective(mesh.vertices, view_matrix, fov, aspect_ratio)
        
        # Calculate bounds dynamically for perspective using a REFERENCE FOV
        # This allows the FOV slider to actually zoom the object in/out visually
        # instead of the auto-framer completely neutralizing the size change.
        reference_fov = 60.0
        verts_2d_ref, _ = project_perspective(mesh.vertices, view_matrix, reference_fov, aspect_ratio)
        
        faces = mesh.faces
        face_z = z_depths[faces] # Use actual Z depths to cull faces behind camera
        valid_faces_mask = np.any(face_z < 0, axis=1)
        valid_tris_ref = verts_2d_ref[faces[valid_faces_mask]]
        
        if len(valid_tris_ref) > 0:
            min_x, min_y = np.min(valid_tris_ref.reshape(-1, 2), axis=0)
            max_x, max_y = np.max(valid_tris_ref.reshape(-1, 2), axis=0)
        else:
            min_x, min_y, max_x, max_y = -1, -1, 1, 1
            
        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2
        range_x = max((max_x - min_x) * 1.05, 1e-5)
        range_y = max((max_y - min_y) * 1.05, 1e-5)
        
        actual_ratio = range_x / range_y
        if actual_ratio < aspect_ratio:
            range_x = range_y * aspect_ratio
        else:
            range_y = range_x / aspect_ratio
            
        return verts_2d, center_x, center_y, range_x, range_y, z_depths
        
    if axis == 'ortho' and camera_settings:
        eye = np.array(camera_settings.get('eye', [0, 17121.782, -3048]))
        target = np.array(camera_settings.get('target', [0, -9144, 7620]))
        up = np.array([0.0, 0.0, 1.0])
        fwd_len = np.linalg.norm(target-eye)
        if fwd_len > 1e-6 and abs(np.dot((target-eye)/fwd_len, up)) > 0.99:
            up = np.array([0.0, 1.0, 0.0])
        
        view_matrix = get_view_matrix(eye, target, up)
        verts_2d, z_depths = project_orthographic(mesh.vertices, view_matrix)
        
        target_ratio = width / height
        
        min_x, min_y = np.min(verts_2d, axis=0)
        max_x, max_y = np.max(verts_2d, axis=0)
        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2
        range_x = max((max_x - min_x) * 1.05, 1)
        range_y = max((max_y - min_y) * 1.05, 1)
        
        actual_ratio = range_x / range_y
        if actual_ratio < target_ratio:
            range_x = range_y * target_ratio
        else:
            range_y = range_x / target_ratio
            
        return verts_2d, center_x, center_y, range_x, range_y, z_depths
        
    if axis == 'x':
        verts_2d = m.vertices[:, [1, 2]]
        verts_2d[:, 0] = -verts_2d[:, 0]
    elif axis == '-x':
        verts_2d = m.vertices[:, [1, 2]]
    elif axis == 'y':
        verts_2d = m.vertices[:, [0, 2]]
    elif axis == '-y':
        verts_2d = m.vertices[:, [0, 2]]
        verts_2d[:, 0] = -verts_2d[:, 0]
    elif axis == 'z':
        verts_2d = m.vertices[:, [0, 1]]
    elif axis == '-z':
        verts_2d = m.vertices[:, [0, 1]]
        verts_2d[:, 1] = -verts_2d[:, 1]
    else:
        raise ValueError(f"Unknown axis {axis}")

    min_x, min_y = np.min(verts_2d, axis=0)
    max_x, max_y = np.max(verts_2d, axis=0)
    center_x = (min_x + max_x) / 2
    center_y = (min_y + max_y) / 2
    range_x = max((max_x - min_x) * 1.05, 1)
    range_y = max((max_y - min_y) * 1.05, 1)
    
    target_ratio = width / height
    actual_ratio = range_x / range_y
    if actual_ratio < target_ratio:
        range_x = range_y * target_ratio
    else:
        range_y = range_x / target_ratio
        
    z_depths = np.dot(mesh.vertices, np.array(normal_map[axis]))
        
    return verts_2d, center_x, center_y, range_x, range_y, z_depths

def extract_occluded_loops(mesh, verts_2d, z_depths, cx, cy, rx, ry, width, height, target_faces_idx):
    import cv2
    dpi = 100
    
    face_z = z_depths[mesh.faces].mean(axis=1)
    sort_idx = np.argsort(face_z)
    
    sorted_faces = mesh.faces[sort_idx]
    sorted_tris = verts_2d[sorted_faces]
    
    colors_pre_sort = np.array(['black'] * len(mesh.faces), dtype=object)
    colors_pre_sort[target_faces_idx] = 'white'
    
    sorted_colors = colors_pre_sort[sort_idx]
    
    fig = plt.figure(figsize=(width / dpi, height / dpi), dpi=dpi)
    fig.patch.set_facecolor('black')
    
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor('black')
    ax.axis('off')
    
    ax.set_xlim(cx - rx / 2, cx + rx / 2)
    ax.set_ylim(cy - ry / 2, cy + ry / 2)
    
    # Render with linewidth 0.5 to prevent artifacts, antialiased=False for sharp edges
    collection = PolyCollection(sorted_tris, facecolors=sorted_colors, edgecolors=sorted_colors, linewidths=0.5, antialiaseds=False)
    ax.add_collection(collection)
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=dpi, transparent=False, facecolor='black')
    plt.close(fig)
    buf.seek(0)
    
    file_bytes = np.asarray(bytearray(buf.read()), dtype=np.uint8)
    img = cv2.imdecode(file_bytes, cv2.IMREAD_GRAYSCALE)
    
    _, thresh = cv2.threshold(img, 127, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    mapped_loops = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < 5: continue
        
        epsilon = 0.001 * cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, epsilon, True)
        
        if len(approx) < 3: continue
        
        loop = []
        for pt in approx:
            px = float(pt[0][0])
            py = float(pt[0][1])
            loop.append((px, py))
        
        mapped_loops.append(loop)
        
    return mapped_loops

def render_axis(mesh, axis, width, height, valid_faces=None, color_mode='black', camera_settings=None):
    m = mesh.copy()
    verts_2d, center_x, center_y, range_x, range_y, z_depths = get_transform_params(mesh, axis, width, height, camera_settings)

    if axis == 'perspective':
        if valid_faces is not None:
            target_faces_idx = valid_faces
        else:
            # For perspective, visible faces are those in front of camera
            face_z = z_depths[mesh.faces]
            target_faces_idx = np.where(np.any(face_z < 0, axis=1))[0]
            
            # Backface culling
            v0 = verts_2d[mesh.faces[target_faces_idx, 0]]
            v1 = verts_2d[mesh.faces[target_faces_idx, 1]]
            v2 = verts_2d[mesh.faces[target_faces_idx, 2]]
            cross = (v1[:, 0] - v0[:, 0]) * (v2[:, 1] - v0[:, 1]) - (v1[:, 1] - v0[:, 1]) * (v2[:, 0] - v0[:, 0])
            front_facing = cross > 0
            target_faces_idx = target_faces_idx[front_facing]
            
        tris = verts_2d[m.faces[target_faces_idx]]
        facecolors = 'black'
    else:
        target_normal = np.array(normal_map[axis])
        
        if valid_faces is not None:
            target_faces_idx = valid_faces
        else:
            dots = np.dot(mesh.face_normals, target_normal)
            target_faces_idx = np.where(dots > 0.0)[0]
            
        if len(target_faces_idx) == 0: return None

        face_centers = mesh.triangles_center[target_faces_idx]
        raw_depths = np.dot(face_centers, target_normal)
        
        depths = cluster_depths(raw_depths, threshold=0.005)
        
        sort_idx = np.argsort(depths)
        sorted_faces_idx = target_faces_idx[sort_idx]
        sorted_depths = depths[sort_idx]
        
        tris = verts_2d[m.faces[sorted_faces_idx]]
        
        if color_mode == 'grayscale':
            all_depths = np.dot(mesh.triangles_center, target_normal)
            clustered_all_depths = cluster_depths(all_depths, threshold=0.005)
            
            min_depth = np.min(clustered_all_depths)
            max_depth = np.max(clustered_all_depths)
            
            normalized = np.clip((sorted_depths - min_depth) / (max_depth - min_depth + 1e-9), 0.0, 1.0)
            facecolors = [str(round(d, 4)) for d in normalized]
        else:
            facecolors = 'black'

    if len(tris) == 0: return None

    dpi = 100
    fig = plt.figure(figsize=(width / dpi, height / dpi), dpi=dpi)
    fig.patch.set_facecolor('white')
    
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor('white')
    ax.axis('off')
    
    ax.set_xlim(center_x - range_x / 2, center_x + range_x / 2)
    ax.set_ylim(center_y - range_y / 2, center_y + range_y / 2)
    
    collection = PolyCollection(tris, facecolors=facecolors, edgecolors=facecolors, linewidths=0.8, antialiaseds=False)
    ax.add_collection(collection)
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=dpi, transparent=False, facecolor='white')
    plt.close(fig)
    buf.seek(0)
    img = Image.open(buf).convert('RGB')
    return img

def generate_export_previews(filepath, selected_nodes, hidden_groups=None, hidden_bodies=None, camera_settings=None, is_layer_ids=False, ortho_settings=None, cull_backfaces=True):
    # Calculate global bounds for consistent centering
    full_mesh, face_mapping, scene = load_mesh(filepath, hidden_groups, hidden_bodies, return_face_mapping=True)
    if len(full_mesh.vertices) == 0:
        return []
        
    verts_2d, global_cx, global_cy, global_rx, global_ry, z_depths = get_transform_params(full_mesh, 'perspective', 500, 375, camera_settings)
    ortho_verts_2d, ortho_cx, ortho_cy, ortho_rx, ortho_ry, _ = get_transform_params(full_mesh, 'ortho', 500, 375, camera_settings=ortho_settings)
    
    layers = []
    dpi = 100
    
    def render_faces(verts, faces, cx, cy, rx, ry):
        fig = plt.figure(figsize=(500 / dpi, 375 / dpi), dpi=dpi)
        fig.patch.set_facecolor('white')
        
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_facecolor('white')
        ax.axis('off')
        
        ax.set_xlim(cx - rx / 2, cx + rx / 2)
        ax.set_ylim(cy - ry / 2, cy + ry / 2)
        
        tris = verts[faces]
        collection = PolyCollection(tris, facecolors='black', edgecolors='black', linewidths=0.8, antialiaseds=False)
        ax.add_collection(collection)
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=dpi, transparent=False, facecolor='white')
        plt.close(fig)
        
        b_buf = io.BytesIO()
        Image.open(buf).convert('RGB').save(b_buf, format="PNG")
        return base64.b64encode(b_buf.getvalue()).decode('utf-8')
    
    target_nodes_to_process = []
    if is_layer_ids:
        # If we passed layer IDs, we want to iterate all face_mappings and filter matching layer_ids
        target_nodes_to_process = list(face_mapping.keys())
    else:
        target_set = set()
        for node_id in selected_nodes:
            def get_desc(n):
                target_set.add(n)
                for child in scene.graph.transforms.children.get(n, []):
                    get_desc(child)
            get_desc(node_id)
        target_nodes_to_process = list(target_set)
            
    for desc_node in target_nodes_to_process:
        if desc_node not in face_mapping:
            continue
            
        for mat_name, face_indices in face_mapping[desc_node].items():
            layer_id = f"{desc_node}_{mat_name}"
            if is_layer_ids and layer_id not in selected_nodes:
                continue
                    
            t_faces = np.array(face_indices)
            
            # Filter for front-facing faces only (Perspective)
            face_z = z_depths[full_mesh.faces[t_faces]]
            front_t_faces_idx = np.where(np.any(face_z < 0, axis=1))[0]
            
            if len(front_t_faces_idx) == 0:
                continue
                
            t_faces_front = t_faces[front_t_faces_idx]
            
            if cull_backfaces:
                v0 = verts_2d[full_mesh.faces[t_faces_front, 0]]
                v1 = verts_2d[full_mesh.faces[t_faces_front, 1]]
                v2 = verts_2d[full_mesh.faces[t_faces_front, 2]]
                cross = (v1[:, 0] - v0[:, 0]) * (v2[:, 1] - v0[:, 1]) - (v1[:, 1] - v0[:, 1]) * (v2[:, 0] - v0[:, 0])
                front_facing = cross > 0
                t_faces_front = t_faces_front[front_facing]
                
                if len(t_faces_front) == 0:
                    continue
                
            b64_output = render_faces(verts_2d, full_mesh.faces[t_faces_front], global_cx, global_cy, global_rx, global_ry)
            b64_input = render_faces(ortho_verts_2d, full_mesh.faces[t_faces_front], ortho_cx, ortho_cy, ortho_rx, ortho_ry)
            
            layer_name = f"{desc_node}_{mat_name}"
            layers.append({
                "id": layer_name, 
                "label": layer_name, 
                "src_output": f"data:image/png;base64,{b64_output}",
                "src_input": f"data:image/png;base64,{b64_input}"
            })
        
    return layers

def create_resolume_xml(screen_data_list, width, height, filepath):
    import copy
    template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_outputs", "Test Layout.xml")
    if not os.path.exists(template_path):
        print(f"Warning: the preset template {template_path} does not exist. XML cannot be compiled securely.")
        return
        
    tree = ET.parse(template_path)
    root = tree.getroot()
    screens_parent = root.find('.//screens')
    if screens_parent is None:
        raise Exception("screens_parent not found in XML template")
        
    screens = screens_parent.findall('Screen')
    if not screens:
        raise Exception("No Screen elements found in XML template")
        
    tmpl_screen = copy.deepcopy(screens[0])
    
    # Remove existing screens
    for s in screens:
        screens_parent.remove(s)
        
    for idx, polygon_data in enumerate(screen_data_list):
        new_screen = copy.deepcopy(tmpl_screen)
        uid = str(random.randint(1000000000000, 9999999999999))
        new_screen.set('uniqueId', uid)
        new_screen.set('name', f"Screen {idx + 1}")
        
        name_param = new_screen.find('.//Params[@name="Params"]/Param[@name="Name"]')
        if name_param is not None:
            name_param.set('value', f"Screen {idx + 1}")
            
        layers = new_screen.find('layers')
        tmpl_poly = layers.find('Polygon')
        tmpl_slice = layers.find('Slice')
        layers.clear()
        
        for poly_entry in polygon_data:
            layer_id = poly_entry['layer_id']
            layer_name = poly_entry.get('name') or layer_id
            safe_layer_name = "".join([c if c.isalnum() or c in "-_ " else "_" for c in layer_name]).strip()
            
            input_source = poly_entry.get('input_source') or "0:1"
            resolume_loops = poly_entry.get('resolume_loops') or []
            
            for loop_idx, loop_data in enumerate(resolume_loops):
                in_loop = loop_data.get('input', [])
                out_loop = loop_data.get('output', [])
                
                # Clean up loops that natively connected the first and last point (Resolume handles closures)
                if len(out_loop) > 3 and out_loop[0] == out_loop[-1]:
                    in_loop = in_loop[:-1]
                    out_loop = out_loop[:-1]
                    
                if len(out_loop) < 3: continue
                    
                uid = str(random.randint(1000000000000, 9999999999999))
                
                # Compute Bounds
                in_xs = [pt[0] for pt in in_loop]
                in_ys = [pt[1] for pt in in_loop]
                in_min_x, in_max_x = min(in_xs), max(in_xs)
                in_min_y, in_max_y = min(in_ys), max(in_ys)
    
                out_xs = [pt[0] for pt in out_loop]
                out_ys = [pt[1] for pt in out_loop]
                out_min_x, out_max_x = min(out_xs), max(out_xs)
                out_min_y, out_max_y = min(out_ys), max(out_ys)

                if len(in_loop) == 4 and tmpl_slice is not None:
                    new_item = copy.deepcopy(tmpl_slice)
                    new_item.set("uniqueId", uid)
                    
                    # Map Properties
                    params = new_item.find('.//Params[@name="Common"]')
                    if params is not None:
                        for param in params.findall('Param'):
                            if param.get('name') == 'Name':
                                param.set('value', f"{safe_layer_name}_{loop_idx}")
                                
                    in_params = new_item.find('.//Params[@name="Input"]')
                    if in_params is not None:
                        for param in in_params.findall('ParamChoice'):
                            if param.get('name') == 'Input Source':
                                param.set('value', input_source)
                                param.set('default', input_source)
                    
                    rect = new_item.find('InputRect')
                    if rect is not None:
                        rect.clear()
                        rect.set('orientation', "0")
                        ET.SubElement(rect, "v", x=str(round(in_min_x,2)), y=str(round(in_min_y,2)))
                        ET.SubElement(rect, "v", x=str(round(in_max_x,2)), y=str(round(in_min_y,2)))
                        ET.SubElement(rect, "v", x=str(round(in_max_x,2)), y=str(round(in_max_y,2)))
                        ET.SubElement(rect, "v", x=str(round(in_min_x,2)), y=str(round(in_max_y,2)))
                    
                    rect = new_item.find('OutputRect')
                    if rect is not None:
                        rect.clear()
                        rect.set('orientation', "0")
                        ET.SubElement(rect, "v", x=str(round(out_min_x,2)), y=str(round(out_min_y,2)))
                        ET.SubElement(rect, "v", x=str(round(out_max_x,2)), y=str(round(out_min_y,2)))
                        ET.SubElement(rect, "v", x=str(round(out_max_x,2)), y=str(round(out_max_y,2)))
                        ET.SubElement(rect, "v", x=str(round(out_min_x,2)), y=str(round(out_max_y,2)))
                        
                    homography = new_item.find('.//Homography')
                    if homography is not None:
                        for tag in ['src', 'dst']:
                            p_node = homography.find(tag)
                            if p_node is not None:
                                p_node.clear()
                                ET.SubElement(p_node, "v", x=str(round(out_min_x,2)), y=str(round(out_min_y,2)))
                                ET.SubElement(p_node, "v", x=str(round(out_max_x,2)), y=str(round(out_min_y,2)))
                                ET.SubElement(p_node, "v", x=str(round(out_max_x,2)), y=str(round(out_max_y,2)))
                                ET.SubElement(p_node, "v", x=str(round(out_min_x,2)), y=str(round(out_max_y,2)))
                                
                    point_mode = new_item.find('.//Warper/Params[@name="Warper"]/ParamChoice[@name="Point Mode"]')
                    if point_mode is not None:
                        point_mode.set('value', 'PM_BEZIER')
                        
                    bezier_warper = new_item.find('.//BezierWarper')
                    if bezier_warper is not None:
                        bw_verts = bezier_warper.find('vertices')
                        if bw_verts is not None:
                            bw_verts.clear()
                            
                            tl = min(range(4), key=lambda i: out_loop[i][0] + out_loop[i][1])
                            br = max(range(4), key=lambda i: out_loop[i][0] + out_loop[i][1])
                            tr = max(range(4), key=lambda i: out_loop[i][0] - out_loop[i][1])
                            bl = min(range(4), key=lambda i: out_loop[i][0] - out_loop[i][1])
                            
                            ordered_loop = [out_loop[tl], out_loop[tr], out_loop[br], out_loop[bl]]
                            
                            A, B, C, D = ordered_loop[0], ordered_loop[1], ordered_loop[2], ordered_loop[3]
                            for v_idx in range(4):
                                v = v_idx / 3.0
                                for u_idx in range(4):
                                    u = u_idx / 3.0
                                    px = (1-u)*(1-v)*A[0] + u*(1-v)*B[0] + u*v*C[0] + (1-u)*v*D[0]
                                    py = (1-u)*(1-v)*A[1] + u*(1-v)*B[1] + u*v*C[1] + (1-u)*v*D[1]
                                    ET.SubElement(bw_verts, "v", x=str(round(px, 2)), y=str(round(py, 2)))
                                    
                    layers.append(new_item)
                else:
                    new_item = copy.deepcopy(tmpl_poly)
                    new_item.set("uniqueId", uid)
                    
                    # Map Properties
                    params = new_item.find('.//Params[@name="Common"]')
                    if params is not None:
                        for param in params.findall('Param'):
                            if param.get('name') == 'Name':
                                param.set('value', f"{safe_layer_name}_{loop_idx}")
                                
                    in_params = new_item.find('.//Params[@name="Input"]')
                    if in_params is not None:
                        for param in in_params.findall('ParamChoice'):
                            if param.get('name') == 'Input Source':
                                param.set('value', input_source)
                                param.set('default', input_source)
                    
                    rect = new_item.find('InputRect')
                    if rect is not None:
                        rect.clear()
                        rect.set('orientation', "0")
                        ET.SubElement(rect, "v", x=str(round(in_min_x,2)), y=str(round(in_min_y,2)))
                        ET.SubElement(rect, "v", x=str(round(in_max_x,2)), y=str(round(in_min_y,2)))
                        ET.SubElement(rect, "v", x=str(round(in_max_x,2)), y=str(round(in_max_y,2)))
                        ET.SubElement(rect, "v", x=str(round(in_min_x,2)), y=str(round(in_max_y,2)))
        
                    rect = new_item.find('OutputRect')
                    if rect is not None:
                        rect.clear()
                        rect.set('orientation', "0")
                        ET.SubElement(rect, "v", x=str(round(out_min_x,2)), y=str(round(out_min_y,2)))
                        ET.SubElement(rect, "v", x=str(round(out_max_x,2)), y=str(round(out_min_y,2)))
                        ET.SubElement(rect, "v", x=str(round(out_max_x,2)), y=str(round(out_max_y,2)))
                        ET.SubElement(rect, "v", x=str(round(out_min_x,2)), y=str(round(out_max_y,2)))
                        
                    # Inject Contours
                    contour = new_item.find('InputContour')
                    if contour is not None:
                        pts_node = contour.find('points')
                        pts_node.clear()
                        for pt in in_loop:
                            ET.SubElement(pts_node, "v", x=str(round(pt[0],2)), y=str(round(pt[1],2)))
                        segments_node = contour.find('segments')
                        segments_node.text = "L" * len(in_loop)
        
                    contour = new_item.find('OutputContour')
                    if contour is not None:
                        pts_node = contour.find('points')
                        pts_node.clear()
                        for pt in out_loop:
                            ET.SubElement(pts_node, "v", x=str(round(pt[0],2)), y=str(round(pt[1],2)))
                        segments_node = contour.find('segments')
                        segments_node.text = "L" * len(out_loop)
                            
                    layers.append(new_item)
                
        screens_parent.append(new_screen)
        
    tree.write(filepath, pretty_print=True, xml_declaration=True, encoding="utf-8")

def polygon_area(pts):
    if len(pts) < 3: return 0.0
    area = 0.0
    for i in range(len(pts)):
        j = (i + 1) % len(pts)
        area += pts[i][0] * pts[j][1] - pts[j][0] * pts[i][1]
    return abs(area) / 2.0

def extract_loops(faces):
    if len(faces) == 0: return []
    edges = np.vstack([
        faces[:, [0, 1]],
        faces[:, [1, 2]],
        faces[:, [2, 0]]
    ])
    
    edges.sort(axis=1)
    unique_edges, counts = np.unique(edges, axis=0, return_counts=True)
    boundary_edges = unique_edges[counts == 1]
    
    edge_list = [set(edge) for edge in boundary_edges]
    loops = []
    
    while edge_list:
        current_edge = edge_list.pop(0)
        u, v = list(current_edge)
        loop = [u, v]
        
        while True:
            found_next = False
            for i, e in enumerate(edge_list):
                if v in e:
                    edge_list.pop(i)
                    v = list(e - {v})[0]
                    loop.append(v)
                    found_next = True
                    break
            if not found_next:
                for i, e in enumerate(edge_list):
                    if u in e:
                        edge_list.pop(i)
                        u = list(e - {u})[0]
                        loop.insert(0, u)
                        found_next = True
                        break
            if not found_next:
                break
        loops.append(loop)
        
    return loops

def get_resolume_polygon_data(filepath, selected_nodes, width, height, hidden_groups=None, hidden_bodies=None, camera_settings=None, is_layer_ids=False, ortho_settings=None, cull_backfaces=True):
    full_mesh, face_mapping, scene = load_mesh(filepath, hidden_groups, hidden_bodies, return_face_mapping=True)
    if len(full_mesh.vertices) == 0:
        return []
        
    verts_2d, global_cx, global_cy, global_rx, global_ry, z_depths = get_transform_params(full_mesh, 'perspective', width, height, camera_settings)
    ortho_verts_2d, ortho_cx, ortho_cy, ortho_rx, ortho_ry, _ = get_transform_params(full_mesh, 'ortho', width, height, camera_settings=ortho_settings)
    resolume_polygon_data = []
    
    def get_pixel_coords(verts, cx, cy, rx, ry, w, h):
        min_x, min_y = cx - rx / 2, cy - ry / 2
        px = ((verts[:, 0] - min_x) / rx) * w
        py = ((verts[:, 1] - min_y) / ry) * h
        py = h - py
        return np.column_stack((px, py))
    
    target_nodes_to_process = []
    if is_layer_ids:
        target_nodes_to_process = list(face_mapping.keys())
    else:
        target_set = set()
        for node_id in selected_nodes:
            def get_desc(n):
                target_set.add(n)
                for child in scene.graph.transforms.children.get(n, []):
                    get_desc(child)
            get_desc(node_id)
        target_nodes_to_process = list(target_set)
            
    for desc_node in target_nodes_to_process:
        if desc_node not in face_mapping:
            continue
            
        for mat_name, face_indices in face_mapping[desc_node].items():
            layer_id = f"{desc_node}_{mat_name}"
            if is_layer_ids and layer_id not in selected_nodes:
                continue
                
            if not face_indices:
                continue
                    
            t_faces = np.array(face_indices)
            
            # Filter for front-facing faces only
            face_z = z_depths[full_mesh.faces[t_faces]]
            front_t_faces_idx = np.where(np.any(face_z < 0, axis=1))[0]
            
            if len(front_t_faces_idx) == 0:
                continue
                
            t_faces = t_faces[front_t_faces_idx]
                
            if cull_backfaces:
                v0 = verts_2d[full_mesh.faces[t_faces, 0]]
                v1 = verts_2d[full_mesh.faces[t_faces, 1]]
                v2 = verts_2d[full_mesh.faces[t_faces, 2]]
                cross = (v1[:, 0] - v0[:, 0]) * (v2[:, 1] - v0[:, 1]) - (v1[:, 1] - v0[:, 1]) * (v2[:, 0] - v0[:, 0])
                front_facing = cross > 0
                t_faces = t_faces[front_facing]
                
                if len(t_faces) == 0: continue
            
            # For XML Polygons, use topological boundary of front-facing triangles
            topological_loops = extract_loops(full_mesh.faces[t_faces])
            resolume_mapped_loops = []
            for loop_idx in topological_loops:
                p_loop = get_pixel_coords(verts_2d[loop_idx], global_cx, global_cy, global_rx, global_ry, width, height).tolist()
                o_loop = get_pixel_coords(ortho_verts_2d[loop_idx], ortho_cx, ortho_cy, ortho_rx, ortho_ry, width, height).tolist()
                
                if polygon_area(o_loop) <= 1.0 or polygon_area(p_loop) <= 1.0:
                    continue
                    
                # Simplify using approxPolyDP
                import cv2
                out_arr = np.array(p_loop, dtype=np.float32)
                epsilon = 2.0  # 2 pixels tolerance
                approx = cv2.approxPolyDP(out_arr, epsilon, True)
                
                if len(approx) < 3:
                    continue
                    
                simplified_indices = []
                for pt in approx:
                    dists = np.sum((out_arr - pt[0])**2, axis=1)
                    idx = np.argmin(dists)
                    simplified_indices.append(idx)
                    
                # Ensure index 0 is present if it's a loop
                in_loop_simp = [o_loop[i] for i in simplified_indices]
                out_loop_simp = [p_loop[i] for i in simplified_indices]
                
                # Remove redundant start/end point if it exists
                if len(in_loop_simp) > 3 and abs(in_loop_simp[0][0] - in_loop_simp[-1][0]) < 0.5 and abs(in_loop_simp[0][1] - in_loop_simp[-1][1]) < 0.5:
                    in_loop_simp.pop()
                    out_loop_simp.pop()
                    
                if len(in_loop_simp) < 3:
                    continue
                    
                # Perturb any consecutive identical points to prevent Resolume triangulator crash
                for i in range(1, len(in_loop_simp)):
                    if abs(in_loop_simp[i][0] - in_loop_simp[i-1][0]) < 0.5 and abs(in_loop_simp[i][1] - in_loop_simp[i-1][1]) < 0.5:
                        in_loop_simp[i] = [in_loop_simp[i][0] + 0.5, in_loop_simp[i][1] + 0.5]
                    if abs(out_loop_simp[i][0] - out_loop_simp[i-1][0]) < 0.5 and abs(out_loop_simp[i][1] - out_loop_simp[i-1][1]) < 0.5:
                        out_loop_simp[i] = [out_loop_simp[i][0] + 0.5, out_loop_simp[i][1] + 0.5]
                        
                def signed_area(pts):
                    if len(pts) < 3: return 0.0
                    area = 0.0
                    for k in range(len(pts)):
                        j = (k + 1) % len(pts)
                        area += pts[k][0] * pts[j][1] - pts[j][0] * pts[k][1]
                    return area
                    
                if abs(signed_area(in_loop_simp)) < 1.0 or abs(signed_area(out_loop_simp)) < 1.0:
                    continue
                    
                if signed_area(in_loop_simp) * signed_area(out_loop_simp) < 0:
                    in_loop_simp = in_loop_simp[::-1]
                    
                def is_valid_loop(loop):
                    return all(not (math.isnan(pt[0]) or math.isnan(pt[1]) or math.isinf(pt[0]) or math.isinf(pt[1])) for pt in loop)
                    
                if not is_valid_loop(in_loop_simp) or not is_valid_loop(out_loop_simp):
                    continue
                        
                resolume_mapped_loops.append({"input": in_loop_simp, "output": out_loop_simp})
                
            final_mapped_loops = [rml["output"] for rml in resolume_mapped_loops]
            
            # Only add if we have valid loops
            if final_mapped_loops or resolume_mapped_loops:
                layer_name = f"{desc_node}_{mat_name}"
                resolume_polygon_data.append({
                    "layer_id": layer_name,
                    "loops": final_mapped_loops,
                    "resolume_loops": resolume_mapped_loops
                })
        
    return resolume_polygon_data

def process_export(filepath, layer_configs, width, height, output_dir, base_name="export", hidden_groups=None, hidden_bodies=None, camera_settings=None, ortho_settings=None, cull_backfaces=True):
    """
    layer_configs is expected to be a list of dicts:
    [{"id": "layer_id", "name": "custom string", "input_source": "0:1"}]
    """
    selected_layer_ids = [lc['id'] for lc in layer_configs]
    config_map = {lc['id']: lc for lc in layer_configs}
    
    mesh = load_mesh(filepath, hidden_groups, hidden_bodies)
    exported_files = []
    
    screen_data_list = []
    
    base_resolume_polygon_data = get_resolume_polygon_data(filepath, selected_layer_ids, width, height, hidden_groups, hidden_bodies, camera_settings, is_layer_ids=True, ortho_settings=ortho_settings, cull_backfaces=cull_backfaces)
    for p_data in base_resolume_polygon_data:
        cfg = config_map.get(p_data["layer_id"], {})
        p_data["name"] = cfg.get("name") or p_data["layer_id"]
        p_data["input_source"] = cfg.get("input_source") or "0:1"
        
    screen_data_list.append(base_resolume_polygon_data)
    
    if camera_settings and camera_settings.get('perspective'):
        import copy
        mirrored_settings = copy.deepcopy(camera_settings)
        mirrored_settings['perspective']['eye'][0] = -mirrored_settings['perspective']['eye'][0]
        mirrored_settings['perspective']['target'][0] = -mirrored_settings['perspective']['target'][0]
        
        mirrored_data = get_resolume_polygon_data(filepath, selected_layer_ids, width, height, hidden_groups, hidden_bodies, mirrored_settings, is_layer_ids=True, ortho_settings=ortho_settings, cull_backfaces=cull_backfaces)
        for p_data in mirrored_data:
            cfg = config_map.get(p_data["layer_id"], {})
            p_data["name"] = cfg.get("name") or p_data["layer_id"]
            p_data["input_source"] = cfg.get("input_source") or "0:1"
            
        screen_data_list.append(mirrored_data)
        
    # We generate raster images for the zip
    layers_img_data = generate_export_previews(filepath, selected_layer_ids, hidden_groups, hidden_bodies, camera_settings, is_layer_ids=True, ortho_settings=ortho_settings, cull_backfaces=cull_backfaces)
    
    for l_data in layers_img_data:
        layer_id = l_data["id"]
        custom_name = config_map.get(layer_id, {}).get("name") or layer_id
        safe_name = "".join([c if c.isalnum() or c in "-_ " else "_" for c in custom_name]).strip()
        safe_name = safe_name.replace(' ', '_').lower()

        # Output Perspective Mask
        img_b64 = l_data["src_output"].split(',')[1]
        img_data = base64.b64decode(img_b64)
        img = Image.open(io.BytesIO(img_data)).resize((width, height), Image.Resampling.LANCZOS)
        
        fn = f"{base_name}_{safe_name}_output.png"
        path = os.path.join(output_dir, fn)
        img.save(path, format="PNG")
        exported_files.append(path)
        
        inv = ImageOps.invert(img)
        fn_inv = f"{base_name}_{safe_name}_output_inverted.png"
        path_inv = os.path.join(output_dir, fn_inv)
        inv.save(path_inv, format="PNG")
        exported_files.append(path_inv)

        # Input Ortho Mask
        img_b64_in = l_data["src_input"].split(',')[1]
        img_data_in = base64.b64decode(img_b64_in)
        img_in = Image.open(io.BytesIO(img_data_in)).resize((width, height), Image.Resampling.LANCZOS)
        
        fn_in = f"{base_name}_{safe_name}_input.png"
        path_in = os.path.join(output_dir, fn_in)
        img_in.save(path_in, format="PNG")
        exported_files.append(path_in)
                
    if screen_data_list and screen_data_list[0]:
        xml_path = os.path.join(output_dir, f"{base_name}_resolume_layout.xml")
        create_resolume_xml(screen_data_list, width, height, xml_path)
        exported_files.append(xml_path)
        
    return exported_files

