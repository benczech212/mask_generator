import xml.etree.ElementTree as ET

tree = ET.parse('test_outputs/Octagon_Full_masks (2)/Octagon_Full_resolume_layout.xml')
root = tree.getroot()

def polygon_area(pts):
    if len(pts) < 3: return 0.0
    area = 0.0
    for i in range(len(pts)):
        j = (i + 1) % len(pts)
        area += pts[i][0] * pts[j][1] - pts[j][0] * pts[i][1]
    return abs(area) / 2.0

for poly in root.findall('.//Polygon'):
    layer = poly.find('.//Param[@name="Name"]').get('value')
    for io in ['InputContour', 'OutputContour']:
        for contour in poly.findall(f'.//{io}'):
            pts = contour.find('points')
            if pts is not None:
                parsed_pts = []
                for v in pts.findall('v'):
                    parsed_pts.append((float(v.get('x')), float(v.get('y'))))
                area = polygon_area(parsed_pts)
                if area < 10.0:
                    print(f"Layer {layer} {io} area: {area}")
