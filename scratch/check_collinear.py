import xml.etree.ElementTree as ET
import sys

def collinear(p1, p2, p3):
    return abs(p1[0]*(p2[1]-p3[1]) + p2[0]*(p3[1]-p1[1]) + p3[0]*(p1[1]-p2[1])) < 0.1

tree = ET.parse('/home/benczech/dev/mask_generator/temp_uploads/522918c7-fcbd-442f-a954-9f08f56162d0/exports/Octagon_Full_resolume_layout.xml')
collinear_found = False
for poly in tree.findall('.//Polygon'):
    uid = poly.get('uniqueId')
    
    for contour_name in ['InputContour', 'OutputContour']:
        contour = poly.find(contour_name)
        if contour is not None:
            pts = contour.find('points').findall('v')
            coords = [(float(v.get('x')), float(v.get('y'))) for v in pts]
            
            if len(coords) >= 3:
                for i in range(len(coords)):
                    p1 = coords[i]
                    p2 = coords[(i+1)%len(coords)]
                    p3 = coords[(i+2)%len(coords)]
                    if collinear(p1, p2, p3):
                        print(f'Collinear points in {contour_name} of Polygon {uid}: {p1}, {p2}, {p3}')
                        collinear_found = True

if not collinear_found:
    print('No collinear points found')
