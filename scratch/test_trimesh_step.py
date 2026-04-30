import trimesh
try:
    scene = trimesh.load('temp_uploads/cdb176b3-fe7e-4314-a10c-5796001e6ee0/Octagon_Full.step')
    print("Type:", type(scene))
    if isinstance(scene, trimesh.Scene):
        print("Graph keys:", scene.graph.nodes)
except Exception as e:
    print("Error:", e)
