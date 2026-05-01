from mask_processor import get_resolume_polygon_data, get_scene_hierarchy
import os

filepath = 'examples/Octagon_Full.step'
hierarchy = get_scene_hierarchy(filepath)

# Let's get the nodes that have meshes
target_nodes = []
def get_nodes(h):
    if h.get('has_mesh'):
        target_nodes.append(h['id'])
    for c in h.get('children', []):
        get_nodes(c)
get_nodes(hierarchy)

print("Nodes:", target_nodes)

# We need the actual layer ids, which are f"{node_id}_{mat_name}"
# But we can just use selected_nodes=target_nodes and is_layer_ids=False
camera_settings = {
    'eye': [6552, 15818, -3048],
    'target': [-3499, -8448, 7620],
    'fov': 60
}

data = get_resolume_polygon_data(filepath, target_nodes, 1920, 1080, [], [], camera_settings, is_layer_ids=False, ortho_settings=None, cull_backfaces=True)
print(f"Returned {len(data)} polygons")
