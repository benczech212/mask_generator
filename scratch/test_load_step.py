import re
import numpy as np
import trimesh

def _load_step(filepath):
    import gmsh
    color_to_name = {}
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
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
        gmsh.merge(filepath)
        
        vols = gmsh.model.getEntities(3)
        if not vols: vols = gmsh.model.getEntities(2)
        
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
                
            # Get bounding surfaces
            boundaries = gmsh.model.getBoundary([(dim, tag)], combined=True, oriented=False, recursive=False)
            for b_dim, b_tag in boundaries:
                if b_dim == 2:
                    groups_by_name[matched_name].append(b_tag)
                    
        gmsh.model.mesh.generate(2)
        
        nodeTags, nodeCoords, _ = gmsh.model.mesh.getNodes()
        node_map = {tag: i for i, tag in enumerate(nodeTags)}
        vertices = np.array(nodeCoords).reshape(-1, 3)

        scene = trimesh.Scene()
        
        for name, surf_tags in groups_by_name.items():
            faces = []
            for tag in surf_tags:
                elemTypes, elemTags, elemNodeTags = gmsh.model.mesh.getElements(2, tag)
                for etype, enodes in zip(elemTypes, elemNodeTags):
                    if etype == 2: # 3-node triangle
                        for i in range(0, len(enodes), 3):
                            faces.append([
                                node_map[enodes[i]],
                                node_map[enodes[i+1]],
                                node_map[enodes[i+2]]
                            ])
            if faces:
                mesh = trimesh.Trimesh(vertices=vertices, faces=faces)
                mat = trimesh.visual.material.SimpleMaterial(name=name)
                # Assign simple material to visual
                mesh.visual = trimesh.visual.ColorVisuals(mesh=mesh)
                mesh.visual.material = mat
                scene.add_geometry(mesh, geom_name=f"{name}_{len(scene.geometry)}")
                
        return scene
    finally:
        gmsh.finalize()

scene = _load_step("Octagon Full.step")
print(f"Loaded {len(scene.geometry)} geometries:")
for name, geom in scene.geometry.items():
    print(f"  Name: {name}, Faces: {len(geom.faces)}, Material: {geom.visual.material.name}")
