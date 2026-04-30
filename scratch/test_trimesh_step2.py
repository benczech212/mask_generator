import trimesh
scene = trimesh.load('temp_uploads/cdb176b3-fe7e-4314-a10c-5796001e6ee0/Octagon_Full.step')

def dump_graph(scene, node='world', indent=0):
    geom_name = scene.graph[node][1] if node in scene.graph else None
    print(" " * indent + f"- Node: {node} (Geom: {geom_name})")
    for child in scene.graph.transforms.children.get(node, []):
        dump_graph(scene, child, indent + 2)

dump_graph(scene)
