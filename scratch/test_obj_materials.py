import trimesh
import os

scene = trimesh.load('../Octagon.obj')
print(f"Loaded {len(scene.geometry)} geometries.")

# Check the materials on the geometry
for name, geom in scene.geometry.items():
    mat = geom.visual.material
    print(f"Geometry: {name}, Material Name: {mat.name}, Color: {mat.main_color}")

