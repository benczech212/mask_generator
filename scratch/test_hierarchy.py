import trimesh
import json
scene = trimesh.load('temp_uploads/cdb176b3-fe7e-4314-a10c-5796001e6ee0/Octagon_Full.step')

def build_tree(scene, node='world'):
    geom_name = scene.graph[node][1] if node in scene.graph else None
    children = scene.graph.transforms.children.get(node, [])
    
    result = {
        "id": node,
        "name": node,
        "geom": geom_name,
        "children": []
    }
    
    for child in children:
        result["children"].append(build_tree(scene, child))
        
    return result

tree = build_tree(scene)
print(json.dumps(tree, indent=2))
