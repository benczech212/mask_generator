import gmsh
gmsh.initialize()
try:
    gmsh.option.setNumber("Geometry.OCCImportLabels", 1)
except Exception as e:
    pass
gmsh.merge("Octagon Full.step")

vols = gmsh.model.getEntities(3)
if not vols: vols = gmsh.model.getEntities(2)

for dim, tag in vols:
    name = gmsh.model.getEntityName(dim, tag)
    color = gmsh.model.getColor(dim, tag)
    print(f"Entity {tag}: Name='{name}', Color={color}")

gmsh.finalize()
