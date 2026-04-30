import gmsh
import sys

gmsh.initialize()
gmsh.merge("Octagon Full.step")

# Get all volumes
volumes = gmsh.model.getEntities(3)
if not volumes:
    # Try surfaces if it's a surface model
    volumes = gmsh.model.getEntities(2)

print("Entities:", len(volumes))

# Check physical groups
groups = gmsh.model.getPhysicalGroups()
print("Physical Groups before:", len(groups))

# Let's see if materials are imported as physical groups
# gmsh doesn't automatically create physical groups from step materials unless configured
# Let's check gmsh options
# gmsh.option.setNumber("Geometry.OCCImportLabels", 1) might help?

gmsh.finalize()
