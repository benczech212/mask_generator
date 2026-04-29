import argparse
import sys
import os
import copy
import random
import trimesh
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from PIL import Image, ImageOps
import lxml.etree as ET

def parse_args():
    parser = argparse.ArgumentParser(description="Convert OBJ to silhouette PNG masks and XML layouts grouped by material")
    parser.add_argument("input", help="Path to OBJ file")
    
    # Orthographic args
    parser.add_argument("--axis", choices=['x', '-x', 'y', '-y', 'z', '-z', 'all'], default='z',
                        help="The axis the camera is looking DOWN for orthographic projection.")
    
    # Perspective args
    parser.add_argument("--perspective", action="store_true", help="Render perspective views in addition to orthographic.")
    parser.add_argument("--interactive", action="store_true", help="Open a 3D window to position the camera visually before generating masks.")
    parser.add_argument("--dual-projector", action="store_true", help="Enable Projector 1 & 2 workflow with mirrored cameras and material assignment.")
    parser.add_argument("--camera-pos", type=str, default="50.0,-50.0,50.0", help="Comma separated x,y,z for perspective camera position")
    parser.add_argument("--camera-target", type=str, default="0.0,0.0,0.0", help="Comma separated x,y,z for perspective camera target")
    parser.add_argument("--camera-fov", type=float, default=60.0, help="Camera Field of View in degrees")
    
    parser.add_argument("--width", type=int, default=1920, help="Width of output mask (pixels)")
    parser.add_argument("--height", type=int, default=1080, help="Height of output mask (pixels)")
    return parser.parse_args()

def polygon_area(pts):
    if len(pts) < 3: return 0.0
    area = 0.0
    for i in range(len(pts)):
        j = (i + 1) % len(pts)
        area += pts[i][0] * pts[j][1] - pts[j][0] * pts[i][1]
    return abs(area) / 2.0

def get_ortho_front_faces(geom, axis):
    normal_map = {'x': [1,0,0], '-x': [-1,0,0], 'y': [0,1,0], '-y': [0,-1,0], 'z': [0,0,1], '-z': [0,0,-1]}
    target_normal = np.array(normal_map[axis])
    dots = np.dot(geom.face_normals, target_normal)
    return np.where(dots > 0.01)[0]

def get_persp_front_faces(geom, camera_pos):
    view_dirs = camera_pos - geom.triangles_center
    norms = np.linalg.norm(view_dirs, axis=1)
    norms[norms == 0] = 1 # prevent division by zero
    view_dirs = view_dirs / norms[:, None]
    dots = np.sum(geom.face_normals * view_dirs, axis=1)
    return np.where(dots > 0.01)[0]

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

def get_perspective_projection(vertices, fov_deg, aspect, near, far, camera_pos, camera_target, up_vector):
    fov = np.radians(fov_deg)
    
    zaxis = camera_pos - camera_target
    norm_z = np.linalg.norm(zaxis)
    if norm_z == 0:
        zaxis = np.array([0.0, 0.0, 1.0])
    else:
        zaxis = zaxis / norm_z
        
    xaxis = np.cross(up_vector, zaxis)
    norm_x = np.linalg.norm(xaxis)
    if norm_x == 0:
        xaxis = np.array([1.0, 0.0, 0.0])
    else:
        xaxis = xaxis / norm_x
        
    yaxis = np.cross(zaxis, xaxis)
    
    view_mat = np.eye(4)
    view_mat[0, :3] = xaxis
    view_mat[1, :3] = yaxis
    view_mat[2, :3] = zaxis
    view_mat[0, 3] = -np.dot(xaxis, camera_pos)
    view_mat[1, 3] = -np.dot(yaxis, camera_pos)
    view_mat[2, 3] = -np.dot(zaxis, camera_pos)
    
    f = 1.0 / np.tan(fov / 2.0)
    proj_mat = np.zeros((4, 4))
    proj_mat[0, 0] = f / aspect
    proj_mat[1, 1] = f
    proj_mat[2, 2] = (near + far) / (near - far)
    proj_mat[2, 3] = (2 * near * far) / (near - far)
    proj_mat[3, 2] = -1.0
    
    ones = np.ones((len(vertices), 1))
    v4 = np.hstack([vertices, ones])
    
    v4_view = v4 @ view_mat.T
    v4_proj = v4_view @ proj_mat.T
    
    v2_proj = v4_proj[:, :2] / v4_proj[:, 3:4]
    return v2_proj

def create_camera_transform(camera_pos, camera_target, up_vector):
    zaxis = camera_pos - camera_target
    norm_z = np.linalg.norm(zaxis)
    zaxis = zaxis / norm_z if norm_z > 0 else np.array([0.0,0.0,1.0])
    
    xaxis = np.cross(up_vector, zaxis)
    norm_x = np.linalg.norm(xaxis)
    xaxis = xaxis / norm_x if norm_x > 0 else np.array([1.0,0.0,0.0])
    
    yaxis = np.cross(zaxis, xaxis)
    
    transform = np.eye(4)
    transform[:3, 0] = xaxis
    transform[:3, 1] = yaxis
    transform[:3, 2] = zaxis
    transform[:3, 3] = camera_pos
    return transform

def get_orthographic_projection(vertices, axis):
    if axis == 'x':
        v2 = vertices[:, [1, 2]]
        v2[:, 0] = -v2[:, 0]
    elif axis == '-x':
        v2 = vertices[:, [1, 2]]
    elif axis == 'y':
        v2 = vertices[:, [0, 2]]
    elif axis == '-y':
        v2 = vertices[:, [0, 2]]
        v2[:, 0] = -v2[:, 0]
    elif axis == 'z':
        v2 = vertices[:, [0, 1]]
    elif axis == '-z':
        v2 = vertices[:, [0, 1]]
        v2[:, 1] = -v2[:, 1]
    else:
        v2 = vertices[:, [0, 1]]
    return v2

def setup_global_bounds(all_v2, width, height, margin=1.05):
    min_x, min_y = np.min(all_v2, axis=0)
    max_x, max_y = np.max(all_v2, axis=0)
    center_x = (min_x + max_x) / 2
    center_y = (min_y + max_y) / 2
    
    range_x = (max_x - min_x) * margin
    range_y = (max_y - min_y) * margin
    
    target_ratio = width / height
    actual_ratio = range_x / range_y if range_y != 0 else 1
    
    if actual_ratio < target_ratio:
        range_x = range_y * target_ratio
    else:
        range_y = range_x / target_ratio
        
    return center_x - range_x / 2, center_x + range_x / 2, center_y - range_y / 2, center_y + range_y / 2

def render_mask(tris, bounds, output_path, width, height):
    dpi = 100
    fig = plt.figure(figsize=(width / dpi, height / dpi), dpi=dpi)
    fig.patch.set_facecolor('white')
    
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor('white')
    ax.axis('off')
    
    ax.set_xlim(bounds[0], bounds[1])
    ax.set_ylim(bounds[2], bounds[3])
    
    collection = PolyCollection(tris, facecolors='black', edgecolors='black', linewidths=0.1)
    ax.add_collection(collection)
    
    plt.savefig(output_path, dpi=dpi, transparent=False, facecolor='white')
    plt.close()
    
    img = Image.open(output_path).convert('RGB')
    inverted_img = ImageOps.invert(img)
    base, ext = os.path.splitext(output_path)
    inverted_img.save(f"{base}_inverted{ext}")

def create_resolume_xml(polygon_data, width, height, filepath):
    # polygon_data can be a list (single screen) or a dict of lists (multi-screen)
    is_multi = isinstance(polygon_data, dict)
    
    template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Test Layout.xml")
    if not os.path.exists(template_path):
        print(f"Warning: the preset template {template_path} does not exist. XML cannot be compiled securely.")
        return
        
    tree = ET.parse(template_path)
    root = tree.getroot()
    screens_container = root.xpath('//screens')
    if not screens_container:
        return
        
    screens_node = screens_container[0]
    tmpl_screen = screens_node.find('Screen')
    if tmpl_screen is None:
        return
        
    screens_node.remove(tmpl_screen)
    
    screens_to_process = polygon_data.items() if is_multi else [("Screen 1", polygon_data)]
    
    for screen_name, poly_list in screens_to_process:
        new_screen = copy.deepcopy(tmpl_screen)
        
        # Rename screen
        params = new_screen.find('.//Params[@name="Common"]')
        if params is not None:
            for param in params.findall('Param'):
                if param.get('name') == 'Name':
                    param.set('value', screen_name)
                    
        layers = new_screen.find('layers')
        tmpl_poly = layers.find('Polygon')
        
        if tmpl_poly is not None:
            tmpl_poly = copy.deepcopy(tmpl_poly)
            
        layers.clear()
        
        for poly_entry in poly_list:
            layer_name = poly_entry['name']
            input_source = poly_entry.get('input_source', "0:1")
            resolume_loops = poly_entry['resolume_loops']
            
            for loop_idx, loop_data in enumerate(resolume_loops):
                in_loop = loop_data['input']
                out_loop = loop_data['output']
                
                if len(in_loop) > 3 and in_loop[0] == in_loop[-1]:
                    in_loop = in_loop[:-1]
                    out_loop = out_loop[:-1]
                    
                if len(in_loop) < 3: continue
                    
                uid = str(random.randint(1000000000000, 9999999999999))
                
                new_poly = copy.deepcopy(tmpl_poly)
                new_poly.set("uniqueId", uid)
                
                poly_params = new_poly.find('.//Params[@name="Common"]')
                for param in poly_params.findall('Param'):
                    if param.get('name') == 'Name':
                        param.set('value', f"{layer_name}_{loop_idx}")
                        
                in_params = new_poly.find('.//Params[@name="Input"]')
                if in_params is not None:
                    for param in in_params.findall('ParamChoice'):
                        if param.get('name') == 'Input Source':
                            param.set('value', input_source)
                            param.set('default', input_source)
                
                in_xs = [pt[0] for pt in in_loop]
                in_ys = [pt[1] for pt in in_loop]
                in_min_x, in_max_x = min(in_xs), max(in_xs)
                in_min_y, in_max_y = min(in_ys), max(in_ys)
                
                out_xs = [pt[0] for pt in out_loop]
                out_ys = [pt[1] for pt in out_loop]
                out_min_x, out_max_x = min(out_xs), max(out_xs)
                out_min_y, out_max_y = min(out_ys), max(out_ys)
                
                rect = new_poly.find('InputRect')
                if rect is not None:
                    rect.clear()
                    rect.set('orientation', "0")
                    ET.SubElement(rect, "v", x=str(round(in_min_x,2)), y=str(round(in_min_y,2)))
                    ET.SubElement(rect, "v", x=str(round(in_max_x,2)), y=str(round(in_min_y,2)))
                    ET.SubElement(rect, "v", x=str(round(in_max_x,2)), y=str(round(in_max_y,2)))
                    ET.SubElement(rect, "v", x=str(round(in_min_x,2)), y=str(round(in_max_y,2)))
                    
                rect = new_poly.find('OutputRect')
                if rect is not None:
                    rect.clear()
                    rect.set('orientation', "0")
                    ET.SubElement(rect, "v", x=str(round(out_min_x,2)), y=str(round(out_min_y,2)))
                    ET.SubElement(rect, "v", x=str(round(out_max_x,2)), y=str(round(out_min_y,2)))
                    ET.SubElement(rect, "v", x=str(round(out_max_x,2)), y=str(round(out_max_y,2)))
                    ET.SubElement(rect, "v", x=str(round(out_min_x,2)), y=str(round(out_max_y,2)))
                    
                contour = new_poly.find('InputContour')
                if contour is not None:
                    pts_node = contour.find('points')
                    pts_node.clear()
                    for pt in in_loop:
                        ET.SubElement(pts_node, "v", x=str(round(pt[0],2)), y=str(round(pt[1],2)))
                    segments_node = contour.find('segments')
                    segments_node.text = "L" * len(in_loop)
                    
                contour = new_poly.find('OutputContour')
                if contour is not None:
                    pts_node = contour.find('points')
                    pts_node.clear()
                    for pt in out_loop:
                        ET.SubElement(pts_node, "v", x=str(round(pt[0],2)), y=str(round(pt[1],2)))
                    segments_node = contour.find('segments')
                    segments_node.text = "L" * len(out_loop)
                layers.append(new_poly)
                
        screens_node.append(new_screen)

    tree.write(filepath, pretty_print=True, xml_declaration=True, encoding="utf-8")

def map_loops_to_px(loops, v2, bounds, width, height):
    mapped_loops = []
    for loop in loops:
        pts_3d_mapped_to_2d = v2[loop]
        mapped_loop = []
        for pt in pts_3d_mapped_to_2d:
            x_v, y_v = pt[0], pt[1]
            px = ((x_v - bounds[0]) / (bounds[1] - bounds[0])) * width
            py = height - ((y_v - bounds[2]) / (bounds[3] - bounds[2])) * height
            mapped_loop.append((px, py))
        mapped_loops.append(mapped_loop)
    return mapped_loops

def main():
    args = parse_args()
    if not os.path.exists(args.input):
        print(f"File not found: {args.input}")
        sys.exit(1)
        
    base_name = os.path.splitext(os.path.basename(args.input))[0]
    
    print(f"Loading {args.input} via trimesh...")
    scene = trimesh.load(args.input, process=False)
    
    if isinstance(scene, trimesh.Trimesh):
        geometries = {'default': scene}
    else:
        geometries = scene.geometry
        
    print(f"Loaded {len(geometries)} bodies.")
    
    material_groups = {}
    for name, geom in geometries.items():
        mat_name = geom.visual.material.name if hasattr(geom.visual, 'material') and geom.visual.material else 'default'
        if mat_name not in material_groups:
            material_groups[mat_name] = []
        material_groups[mat_name].append(geom)
        
    print(f"Grouped into {len(material_groups)} materials: {list(material_groups.keys())}")
    
    mat_names = list(material_groups.keys())
    
    p1_mats = mat_names
    p2_mats = []
    
    if args.dual_projector:
        print("\n--- Dual Projector Material Setup ---")
        for i, m in enumerate(mat_names):
            print(f"  [{i}] {m}")
        p1_in = input(f"Enter numbers for Projector 1 (comma separated, or 'all'): ").strip()
        p2_in = input(f"Enter numbers for Projector 2 (comma separated, or 'all'): ").strip()
        
        if p1_in.lower() == 'all' or p1_in == '':
            p1_mats = mat_names
        else:
            p1_mats = [mat_names[int(x.strip())] for x in p1_in.split(',') if x.strip().isdigit()]
            
        if p2_in.lower() == 'all':
            p2_mats = mat_names
        else:
            p2_mats = [mat_names[int(x.strip())] for x in p2_in.split(',') if x.strip().isdigit()]
            
    cam1_pos = None
    cam1_target = None
    up1_vector = None
    
    cam2_pos = None
    cam2_target = None
    up2_vector = None
    
    fov = args.camera_fov
    
    group_persp_v2s_p1 = {}
    persp_bounds_p1 = None
    
    group_persp_v2s_p2 = {}
    persp_bounds_p2 = None
    
    if args.perspective or args.interactive or args.dual_projector:
        args.perspective = True # Force perspective
        
        if args.interactive or args.dual_projector:
            print("\nOpening interactive 3D viewer. Position the camera for PROJECTOR 1, then CLOSE the window to continue...")
            
            # Create a temporary scene with distinctly colored geometries for easy viewing
            s = trimesh.Scene()
            for name, geom in geometries.items():
                view_geom = geom.copy()
                view_geom.visual.face_colors = trimesh.visual.random_color()
                s.add_geometry(view_geom, node_name=name)
                
            scene_to_show = s
            scene_to_show.show(resolution=(1280, 720), smooth=False)
            
            transform = scene_to_show.camera_transform
            cam1_pos = transform[:3, 3]
            cam1_target = cam1_pos - transform[:3, 2]
            up1_vector = transform[:3, 1]
            if scene_to_show.camera.fov is not None and len(scene_to_show.camera.fov) > 0:
                fov = scene_to_show.camera.fov[0]
            
            print(f"Projector 1 Camera captured! Pos: {cam1_pos}")
            
            if args.dual_projector:
                cam2_pos = np.array([-cam1_pos[0], cam1_pos[1], cam1_pos[2]])
                cam2_target = np.array([-cam1_target[0], cam1_target[1], cam1_target[2]])
                up2_vector = np.array([-up1_vector[0], up1_vector[1], up1_vector[2]])
                print(f"Projector 2 Camera auto-mirrored! Pos: {cam2_pos}")
                
                print("\nPreviewing Camera for PROJECTOR 2. Close to continue...")
                scene_to_show.camera_transform = create_camera_transform(cam2_pos, cam2_target, up2_vector)
                scene_to_show.show(resolution=(1280, 720), smooth=False)
                
        else:
            cam1_pos = np.array([float(x) for x in args.camera_pos.split(',')])
            cam1_target = np.array([float(x) for x in args.camera_target.split(',')])
            up1_vector = np.array([0.0, 0.0, 1.0])
            
        print("\n--- Pre-computing Perspective ---")
        
        all_persp_v2_p1 = []
        group_persp_tris_p1 = {}
        for mat_name, geoms in material_groups.items():
            if mat_name not in p1_mats: continue
            mat_tris = []
            mat_v2_list = []
            for geom in geoms:
                v2 = get_perspective_projection(geom.vertices, fov, args.width/args.height, 0.1, 1000.0, cam1_pos, cam1_target, up1_vector)
                all_persp_v2_p1.append(v2)
                mat_v2_list.append((geom, v2))
                mat_tris.append(v2[geom.faces])
            if mat_tris:
                group_persp_tris_p1[mat_name] = np.vstack(mat_tris)
                group_persp_v2s_p1[mat_name] = mat_v2_list
            
        if all_persp_v2_p1:
            all_persp_v2_concat_p1 = np.vstack(all_persp_v2_p1)
            persp_bounds_p1 = setup_global_bounds(all_persp_v2_concat_p1, args.width, args.height, margin=1.1)
            
            for mat_name, tris in group_persp_tris_p1.items():
                clean_mat_name = mat_name.replace('/', '_').replace('\\', '_').replace(' ', '_')
                out_path = f"{base_name}_persp1_{clean_mat_name}.png"
                print(f"  -> Rendering P1 perspective mask to {out_path}...")
                render_mask(tris, persp_bounds_p1, out_path, args.width, args.height)

        if args.dual_projector:
            all_persp_v2_p2 = []
            group_persp_tris_p2 = {}
            for mat_name, geoms in material_groups.items():
                if mat_name not in p2_mats: continue
                mat_tris = []
                mat_v2_list = []
                for geom in geoms:
                    v2 = get_perspective_projection(geom.vertices, fov, args.width/args.height, 0.1, 1000.0, cam2_pos, cam2_target, up2_vector)
                    all_persp_v2_p2.append(v2)
                    mat_v2_list.append((geom, v2))
                    mat_tris.append(v2[geom.faces])
                if mat_tris:
                    group_persp_tris_p2[mat_name] = np.vstack(mat_tris)
                    group_persp_v2s_p2[mat_name] = mat_v2_list
                
            if all_persp_v2_p2:
                all_persp_v2_concat_p2 = np.vstack(all_persp_v2_p2)
                persp_bounds_p2 = setup_global_bounds(all_persp_v2_concat_p2, args.width, args.height, margin=1.1)
                
                for mat_name, tris in group_persp_tris_p2.items():
                    clean_mat_name = mat_name.replace('/', '_').replace('\\', '_').replace(' ', '_')
                    out_path = f"{base_name}_persp2_{clean_mat_name}.png"
                    print(f"  -> Rendering P2 perspective mask to {out_path}...")
                    render_mask(tris, persp_bounds_p2, out_path, args.width, args.height)
    
    axes_to_render = ['x', '-x', 'y', '-y', 'z', '-z'] if args.axis == 'all' else [args.axis]
    
    for ax_str in axes_to_render:
        print(f"--- Processing Orthographic: Axis {ax_str} ---")
        
        all_ortho_v2 = []
        group_ortho_tris = {}
        group_ortho_v2s = {}
        for mat_name, geoms in material_groups.items():
            mat_tris = []
            mat_v2_list = []
            for geom in geoms:
                v2 = get_orthographic_projection(geom.vertices, ax_str)
                all_ortho_v2.append(v2)
                mat_v2_list.append((geom, v2))
                mat_tris.append(v2[geom.faces])
            group_ortho_tris[mat_name] = np.vstack(mat_tris)
            group_ortho_v2s[mat_name] = mat_v2_list
            
        all_ortho_v2_concat = np.vstack(all_ortho_v2)
        ortho_bounds = setup_global_bounds(all_ortho_v2_concat, args.width, args.height)
        
        dual_polygon_data = {"Projector 1": [], "Projector 2": []} if args.dual_projector else {"Screen 1": []}
        
        for mat_name, tris in group_ortho_tris.items():
            clean_mat_name = mat_name.replace('/', '_').replace('\\', '_').replace(' ', '_')
            
            # Only render ortho mask if it's used in at least one projector
            if mat_name in p1_mats or mat_name in p2_mats:
                out_path = f"{base_name}_ortho_{ax_str.replace('-', 'neg_')}_{clean_mat_name}.png"
                print(f"  -> Rendering orthographic mask to {out_path}...")
                render_mask(tris, ortho_bounds, out_path, args.width, args.height)
            
            # Projector 1 Processing
            if mat_name in p1_mats:
                mapped_loops_p1 = []
                for i, (geom, ortho_v2) in enumerate(group_ortho_v2s[mat_name]):
                    if args.perspective:
                        front_face_idx = get_persp_front_faces(geom, cam1_pos)
                        if len(front_face_idx) == 0: continue
                        
                        persp_v2 = group_persp_v2s_p1[mat_name][i][1]
                        loops = extract_loops(geom.faces[front_face_idx])
                        
                        ortho_loops = map_loops_to_px(loops, ortho_v2, ortho_bounds, args.width, args.height)
                        persp_loops = map_loops_to_px(loops, persp_v2, persp_bounds_p1, args.width, args.height)
                        
                        for o_loop, p_loop in zip(ortho_loops, persp_loops):
                            if polygon_area(o_loop) > 5.0 and polygon_area(p_loop) > 5.0:
                                mapped_loops_p1.append({
                                    'input': o_loop,
                                    'output': p_loop
                                })
                    else:
                        front_face_idx = get_ortho_front_faces(geom, ax_str)
                        if len(front_face_idx) == 0: continue
                        loops = extract_loops(geom.faces[front_face_idx])
                        ortho_loops = map_loops_to_px(loops, ortho_v2, ortho_bounds, args.width, args.height)
                        
                        for o_loop in ortho_loops:
                            if polygon_area(o_loop) > 5.0:
                                mapped_loops_p1.append({
                                    'input': o_loop,
                                    'output': o_loop
                                })
                
                if args.dual_projector:
                    dual_polygon_data["Projector 1"].append({
                        "layer_id": clean_mat_name,
                        "name": clean_mat_name,
                        "input_source": "0:1",
                        "resolume_loops": mapped_loops_p1
                    })
                else:
                    dual_polygon_data["Screen 1"].append({
                        "layer_id": clean_mat_name,
                        "name": clean_mat_name,
                        "input_source": "0:1",
                        "resolume_loops": mapped_loops_p1
                    })
                    
            # Projector 2 Processing
            if args.dual_projector and mat_name in p2_mats:
                mapped_loops_p2 = []
                for i, (geom, ortho_v2) in enumerate(group_ortho_v2s[mat_name]):
                    front_face_idx = get_persp_front_faces(geom, cam2_pos)
                    if len(front_face_idx) == 0: continue
                    
                    persp_v2 = group_persp_v2s_p2[mat_name][i][1]
                    loops = extract_loops(geom.faces[front_face_idx])
                    
                    ortho_loops = map_loops_to_px(loops, ortho_v2, ortho_bounds, args.width, args.height)
                    persp_loops = map_loops_to_px(loops, persp_v2, persp_bounds_p2, args.width, args.height)
                    
                    for o_loop, p_loop in zip(ortho_loops, persp_loops):
                        if polygon_area(o_loop) > 5.0 and polygon_area(p_loop) > 5.0:
                            mapped_loops_p2.append({
                                'input': o_loop,
                                'output': p_loop
                            })
                            
                dual_polygon_data["Projector 2"].append({
                    "layer_id": clean_mat_name,
                    "name": clean_mat_name,
                    "input_source": "0:1",
                    "resolume_loops": mapped_loops_p2
                })
            
        xml_path = f"{base_name}_ortho_{ax_str.replace('-', 'neg_')}_layout.xml"
        if args.perspective:
            xml_path = f"{base_name}_ortho_{ax_str.replace('-', 'neg_')}_to_persp_layout.xml"
            
        print(f"  -> Generating Resolume XML: {xml_path}...")
        create_resolume_xml(dual_polygon_data, args.width, args.height, xml_path)

    print("Done.")

if __name__ == "__main__":
    main()
