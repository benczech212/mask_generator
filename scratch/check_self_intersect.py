import xml.etree.ElementTree as ET
import shapely.geometry
import sys

tree = ET.parse('/home/benczech/dev/mask_generator/temp_uploads/522918c7-fcbd-442f-a954-9f08f56162d0/exports/Octagon_Full_resolume_layout.xml')
for poly in tree.findall('.//Polygon'):
    uid = poly.get('uniqueId')
    
    for contour_name in ['InputContour', 'OutputContour']:
        contour = poly.find(contour_name)
        if contour is not None:
            pts = contour.find('points').findall('v')
            coords = [(float(v.get('x')), float(v.get('y'))) for v in pts]
            
            if len(coords) >= 3:
                # Add first point to end to close linearring
                coords.append(coords[0])
                ring = shapely.geometry.LinearRing(coords)
                if not ring.is_simple:
                    print(f'Self-intersecting {contour_name} in Polygon {uid}')
                    sys.exit(1)
print('No self-intersections found')
