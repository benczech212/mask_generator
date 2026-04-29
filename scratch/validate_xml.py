import xml.etree.ElementTree as ET

def polygon_area(pts):
    area = 0.0
    for i in range(len(pts)):
        j = (i + 1) % len(pts)
        area += pts[i][0] * pts[j][1] - pts[j][0] * pts[i][1]
    return abs(area) / 2.0

tree = ET.parse('Octagon Full_ortho_z_to_persp_layout.xml')
root = tree.getroot()

layers = root.find('.//layers')
polygons = layers.findall('Polygon')
print(f"Total polygons: {len(polygons)}")

crashes = 0
for i, poly in enumerate(polygons):
    name = poly.find('.//Param[@name="Name"]').get('value')
    for contour_name in ['InputContour', 'OutputContour']:
        contour = poly.find(contour_name)
        if contour is None: continue
        
        pts_node = contour.find('points')
        pts = []
        for v in pts_node.findall('v'):
            pts.append((float(v.get('x')), float(v.get('y'))))
            
        area = polygon_area(pts)
        
        if len(pts) < 3:
            print(f"Polygon {name} {contour_name} has {len(pts)} points! (Needs at least 3)")
            crashes += 1
            continue
            
        if area < 1.0:
            print(f"Polygon {name} {contour_name} has near-zero area: {area}")
            crashes += 1

print(f"Total problematic polygons: {crashes}")
