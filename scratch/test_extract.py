import trimesh
import numpy as np

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

scene = trimesh.load('../Octagon.obj')
for name, geom in scene.geometry.items():
    loops = extract_loops(geom.faces)
    print(f"Geometry {name}: {len(loops)} loops.")
    for i, loop in enumerate(loops[:5]):
        print(f"  Loop {i} length: {len(loop)}")
