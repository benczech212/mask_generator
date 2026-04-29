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

def load_mesh(filepath):
    scene_or_mesh = trimesh.load(filepath, force='mesh')
    if isinstance(scene_or_mesh, trimesh.Scene):
        if not scene_or_mesh.geometry:
            raise ValueError("No geometry found in the file.")
        mesh = trimesh.util.concatenate([g for g in scene_or_mesh.geometry.values()])
    else:
        mesh = scene_or_mesh
    return mesh

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

def get_transform_params(mesh, axis, width, height):
    m = mesh.copy()
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
        
    return verts_2d, center_x, center_y, range_x, range_y

def extract_loops(mesh, valid_faces):
    if len(valid_faces) == 0: return []
    faces = mesh.faces[valid_faces]
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

def render_axis(mesh, axis, width, height, valid_faces=None, color_mode='black'):
    m = mesh.copy()
    verts_2d, center_x, center_y, range_x, range_y = get_transform_params(mesh, axis, width, height)

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

def _get_layers_for_axis(mesh, axes, split_depths):
    idx_map = {'x': 0, '-x': 0, 'y': 1, '-y': 1, 'z': 2, '-z': 2}
    
    for ax in axes:
        yield (f"{ax}_whole", ax, None, f"Whole Mask", 'black')
        yield (f"{ax}_grayscale", ax, None, f"Grayscale Depth Map", 'grayscale')
        
        if split_depths:
            target_normal = normal_map[ax]
            axis_idx = idx_map[ax]
            dots = np.dot(mesh.face_normals, target_normal)
            facing_camera = np.where(dots > 0.99)[0]
            if len(facing_camera) == 0: continue
            
            raw_depths = mesh.triangles_center[facing_camera, axis_idx]
            clustered = cluster_depths(raw_depths, threshold=0.005)
            
            presented_depths = np.round(clustered, 2)
            unique_depths = np.unique(presented_depths)
            
            for d in unique_depths:
                layer_faces = facing_camera[presented_depths == d]
                yield (f"{ax}_depth_{d}", ax, layer_faces, f"Depth {d}", 'black')

def process_preview(filepath):
    mesh = load_mesh(filepath)
    axes = ['x', '-x', 'y', '-y', 'z', '-z']
    previews = {}
    for ax in axes:
        img = render_axis(mesh, ax, 400, 300, color_mode='grayscale')
        if img:
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
            previews[ax] = f"data:image/png;base64,{b64}"
    return previews

def generate_export_previews(filepath, axes_to_render, split_depths):
    mesh = load_mesh(filepath)
    layers = []
    for layer_id, ax, valid_faces, label, c_mode in _get_layers_for_axis(mesh, axes_to_render, split_depths):
        img = render_axis(mesh, ax, 500, 375, valid_faces=valid_faces, color_mode=c_mode)
        if img:
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
            layers.append({"id": layer_id, "axis": ax, "label": label, "src": f"data:image/png;base64,{b64}"})
    return layers

def create_resolume_xml(polygon_data, width, height, filepath):
    import copy
    template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Test Layout.xml")
    if not os.path.exists(template_path):
        print(f"Warning: the preset template {template_path} does not exist. XML cannot be compiled securely.")
        return
        
    tree = ET.parse(template_path)
    root = tree.getroot()
    screens = root.xpath('//screens/Screen')
    if not screens:
        return
        
    screen = screens[0]
    layers = screen.find('layers')
    tmpl_poly = layers.find('Polygon')
    layers.clear()
    
    for poly_entry in polygon_data:
        layer_id = poly_entry['layer_id']
        layer_name = poly_entry.get('name') or layer_id
        input_source = poly_entry.get('input_source') or "0:1"
        resolume_loops = poly_entry.get('resolume_loops') or poly_entry['loops']
        
        for loop_idx, loop in enumerate(resolume_loops):
            # Clean up loops that natively connected the first and last point (Resolume handles closures)
            if len(loop) > 3 and loop[0] == loop[-1]:
                loop = loop[:-1]
                
            if len(loop) < 3: continue
                
            uid = str(random.randint(1000000000000, 9999999999999))
            
            new_poly = copy.deepcopy(tmpl_poly)
            new_poly.set("uniqueId", uid)
            
            # Map Properties
            params = new_poly.find('.//Params[@name="Common"]')
            for param in params.findall('Param'):
                if param.get('name') == 'Name':
                    param.set('value', f"{layer_name}_{loop_idx}")
                    
            in_params = new_poly.find('.//Params[@name="Input"]')
            if in_params is not None:
                for param in in_params.findall('ParamChoice'):
                    if param.get('name') == 'Input Source':
                        param.set('value', input_source)
                        param.set('default', input_source)
            
            # Compute Bounds
            xs = [pt[0] for pt in loop]
            ys = [pt[1] for pt in loop]
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)
            
            # Inject Rects
            for rect_name in ["InputRect", "OutputRect"]:
                rect = new_poly.find(f'{rect_name}')
                if rect is not None:
                    rect.clear()
                    rect.set('orientation', "0")
                    ET.SubElement(rect, "v", x=str(round(min_x,2)), y=str(round(min_y,2)))
                    ET.SubElement(rect, "v", x=str(round(max_x,2)), y=str(round(min_y,2)))
                    ET.SubElement(rect, "v", x=str(round(max_x,2)), y=str(round(max_y,2)))
                    ET.SubElement(rect, "v", x=str(round(min_x,2)), y=str(round(max_y,2)))
                
            # Inject Contours
            for contour_name in ["InputContour", "OutputContour"]:
                contour = new_poly.find(f'{contour_name}')
                if contour is not None:
                    pts_node = contour.find('points')
                    pts_node.clear()
                    for pt in loop:
                        ET.SubElement(pts_node, "v", x=str(round(pt[0],2)), y=str(round(pt[1],2)))
                    
                    segments_node = contour.find('segments')
                    # Format is line sequences. Resolume uses L per vert!
                    segments_node.text = "L" * len(loop)
                    
            layers.append(new_poly)

    tree.write(filepath, pretty_print=True, xml_declaration=True, encoding="utf-8")

def get_resolume_polygon_data(filepath, selected_layer_ids, width, height):
    mesh = load_mesh(filepath)
    resolume_polygon_data = []
    
    axes_needed = []
    for lid in selected_layer_ids:
        if lid.startswith('-'): axes_needed.append('-' + lid.split('_')[1])
        else: axes_needed.append(lid.split('_')[0])
    axes_needed = list(set(axes_needed))
            
    for layer_id, ax, valid_faces, _, _ in _get_layers_for_axis(mesh, axes_needed, split_depths=True):
        if layer_id in selected_layer_ids:
            target_normal = np.array(normal_map[ax])
            if valid_faces is not None:
                t_faces = valid_faces
            else:
                dots = np.dot(mesh.face_normals, target_normal)
                t_faces = np.where(dots > 0.0)[0]
            
            loops = extract_loops(mesh, t_faces)
            verts_2d, cx, cy, rx, ry = get_transform_params(mesh, ax, width, height)
            
            mapped_loops = []
            for loop in loops:
                pts_3d_mapped_to_2d = verts_2d[loop]
                
                mapped_loop = []
                for pt in pts_3d_mapped_to_2d:
                    x_v, y_v = pt[0], pt[1]
                    px = ((x_v - (cx - rx / 2)) / rx) * width
                    py = height - ((y_v - (cy - ry / 2)) / ry) * height
                    mapped_loop.append((px, py))
                mapped_loops.append(mapped_loop)
                
            mapped_resolume_loops = []
            for face_idx in t_faces:
                face_verts = list(mesh.faces[face_idx])
                face_verts.append(face_verts[0])
                
                mapped_rl = []
                for vid in face_verts:
                    pt = verts_2d[vid]
                    px = ((pt[0] - (cx - rx / 2)) / rx) * width
                    py = height - ((pt[1] - (cy - ry / 2)) / ry) * height
                    mapped_rl.append((px, py))
                mapped_resolume_loops.append(mapped_rl)
                
            resolume_polygon_data.append({
                "layer_id": layer_id,
                "loops": mapped_loops,
                "resolume_loops": mapped_resolume_loops
            })
    return resolume_polygon_data

def process_export(filepath, layer_configs, width, height, output_dir, base_name="export"):
    """
    layer_configs is expected to be a list of dicts:
    [{"id": "layer_id", "name": "custom string", "input_source": "0:1"}]
    """
    selected_layer_ids = [lc['id'] for lc in layer_configs]
    config_map = {lc['id']: lc for lc in layer_configs}
    
    mesh = load_mesh(filepath)
    exported_files = []
    
    # 1. Gather all Polygon coordinates via the separated function logic
    # We combine them together with the config map overrides for name/source
    base_resolume_polygon_data = get_resolume_polygon_data(filepath, selected_layer_ids, width, height)
    for p_data in base_resolume_polygon_data:
        cfg = config_map.get(p_data["layer_id"], {})
        p_data["name"] = cfg.get("name") or p_data["layer_id"]
        p_data["input_source"] = cfg.get("input_source") or "0:1"
        
    axes_needed = []
    for lid in selected_layer_ids:
        if lid.startswith('-'): axes_needed.append('-' + lid.split('_')[1])
        else: axes_needed.append(lid.split('_')[0])
    axes_needed = list(set(axes_needed))
            
    # 2. Render discrete PNG masks bounds
    for layer_id, ax, valid_faces, _, c_mode in _get_layers_for_axis(mesh, axes_needed, split_depths=True):
        if layer_id in selected_layer_ids:
            img = render_axis(mesh, ax, width, height, valid_faces=valid_faces, color_mode=c_mode)
            if img:
                custom_name = config_map.get(layer_id, {}).get("name") or layer_id
                # Sanitize out any malicious slash bounds
                safe_name = "".join([c if c.isalnum() or c in "-_ " else "_" for c in custom_name]).strip()
                
                fn = f"{base_name}_{safe_name.replace(' ', '_').lower()}.png"
                path = os.path.join(output_dir, fn)
                img.save(path)
                exported_files.append(path)
                
                inv = ImageOps.invert(img)
                fn_inv = f"{base_name}_{safe_name.replace(' ', '_').lower()}_inverted.png"
                path_inv = os.path.join(output_dir, fn_inv)
                inv.save(path_inv)
                exported_files.append(path_inv)
                
    if base_resolume_polygon_data:
        xml_path = os.path.join(output_dir, f"{base_name}_resolume_layout.xml")
        create_resolume_xml(base_resolume_polygon_data, width, height, xml_path)
        exported_files.append(xml_path)
        
    return exported_files
