import trimesh
import numpy as np
from mask_processor import load_mesh

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
    
    # Store edges in a list of sets for fast lookup/removal
    edge_list = [set(edge) for edge in boundary_edges]
    loops = []
    
    while edge_list:
        # Start a new loop
        current_edge = edge_list.pop(0)
        u, v = list(current_edge)
        loop = [u, v]
        
        while True:
            # Look for an edge that connects to 'v'
            found_next = False
            for i, e in enumerate(edge_list):
                if v in e:
                    edge_list.pop(i)
                    # Next vertex is the one that's not v
                    v = list(e - {v})[0]
                    loop.append(v)
                    found_next = True
                    break
            if not found_next:
                # Look for an edge that connects to 'u' (in case we went the wrong way)
                for i, e in enumerate(edge_list):
                    if u in e:
                        edge_list.pop(i)
                        u = list(e - {u})[0]
                        loop.insert(0, u)
                        found_next = True
                        break
            
            if not found_next:
                # Loop is closed or broken
                break
        loops.append(loop)
        
    return loops

mesh = load_mesh("octagon_segments.3mf")
dots = np.dot(mesh.face_normals, [0,0,1])
facing = np.where(dots > 0.0)[0]
loops = extract_loops(mesh, facing)
print("Found", len(loops), "loops")
for idx, loop in enumerate(loops):
    print(f"Loop {idx}: {len(loop)} points")

