import gmsh
import sys
import trimesh

gmsh.initialize()
gmsh.merge("Octagon Full.step")
gmsh.model.mesh.generate(2)
gmsh.write("scratch/test_export.obj")
gmsh.finalize()

scene = trimesh.load("scratch/test_export.obj")
print("Geometry keys:", scene.geometry.keys() if hasattr(scene, 'geometry') else "Single mesh")
