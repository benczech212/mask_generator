import xml.etree.ElementTree as ET

tree = ET.parse('test_outputs/Octagon_Full_masks/Octagon_Full_resolume_layout.xml')
root = tree.getroot()

max_pts = 0
for poly in root.findall('.//Polygon'):
    layer = poly.find('.//Param[@name="Name"]').get('value')
    for contour in poly.findall('.//InputContour'):
        pts = contour.find('points')
        if pts is not None:
            num_pts = len(pts.findall('v'))
            if num_pts > 0:
                print(f"Layer {layer} InputContour: {num_pts} points")
                max_pts = max(max_pts, num_pts)

print(f"Max points in a single contour: {max_pts}")
