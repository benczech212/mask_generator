import os
import trimesh
import gmsh
import re

def _convert_step_to_obj_with_materials(step_path, obj_path):
    color_to_name = {}
    try:
        with open(step_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        color_pattern = re.compile(r"#\d+\s*=\s*COLOUR_RGB\s*\(\s*'([^']*)'\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*\)\s*;", re.IGNORECASE)
        for match in color_pattern.finditer(content):
            name = match.group(1).strip()
            r = int(round(float(match.group(2)) * 255))
            g = int(round(float(match.group(3)) * 255))
            b = int(round(float(match.group(4)) * 255))
            color_to_name[(r, g, b)] = name
    except Exception:
        pass

    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.merge(step_path)
        
        vols = gmsh.model.getEntities(3)
        
        groups_by_name = {}
        unnamed_counter = 1
        for dim, tag in vols:
            color = gmsh.model.getColor(dim, tag)
            matched_name = f"Unnamed_{unnamed_counter}"
            
            if color and len(color) >= 3 and color != (0,0,0,0):
                rgb = (color[0], color[1], color[2])
                for c_rgb, c_name in color_to_name.items():
                    if abs(c_rgb[0]-rgb[0]) <= 2 and abs(c_rgb[1]-rgb[1]) <= 2 and abs(c_rgb[2]-rgb[2]) <= 2:
                        matched_name = c_name
                        break
            else:
                unnamed_counter += 1
                
            if matched_name not in groups_by_name:
                groups_by_name[matched_name] = []
                
            # Get the surfaces for this volume
            boundaries = gmsh.model.getBoundary([(dim, tag)], combined=True, oriented=False, recursive=False)
            for b_dim, b_tag in boundaries:
                if b_dim == 2:
                    groups_by_name[matched_name].append(b_tag)
            
        print("Groups generated:", list(groups_by_name.keys()))
        for name, tags in groups_by_name.items():
            if tags:
                pg = gmsh.model.addPhysicalGroup(2, tags)
                gmsh.model.setPhysicalName(2, pg, name)
            
        gmsh.model.mesh.generate(2)
        gmsh.write(obj_path)
    finally:
        gmsh.finalize()

_convert_step_to_obj_with_materials("Octagon Full.step", "scratch/test_imported_faces.obj")

scene = trimesh.load("scratch/test_imported_faces.obj")
if isinstance(scene, trimesh.Trimesh):
    print("Loaded as single mesh!")
else:
    print("Loaded as scene! Geometry keys:")
    print(scene.geometry.keys())
    for name, geom in scene.geometry.items():
        mat_name = geom.visual.material.name if hasattr(geom.visual, 'material') and geom.visual.material else 'default'
        print(f"  Geom: {name}, Mat: {mat_name}")
