import matplotlib.pyplot as plt
from shapely.geometry import Polygon

xs, ys = [], []
with open('scratch/plot_poly.py', 'r') as f:
    pass

import xml.etree.ElementTree as ET

tree = ET.parse('test_outputs/Octagon_Full_masks (2)/Octagon_Full_resolume_layout.xml')
root = tree.getroot()

for poly in root.findall('.//Polygon'):
    layer = poly.find('.//Param[@name="Name"]').get('value')
    for io in ['InputContour', 'OutputContour']:
        for contour in poly.findall(f'.//{io}'):
            pts = contour.find('points')
            if pts is not None:
                parsed_pts = []
                for v in pts.findall('v'):
                    parsed_pts.append((float(v.get('x')), float(v.get('y'))))
                if len(parsed_pts) > 3:
                    p = Polygon(parsed_pts)
                    if not p.is_valid:
                        print(f"Layer {layer} {io} is NOT VALID (likely self-intersecting)")
                    if not p.is_simple:
                        print(f"Layer {layer} {io} is NOT SIMPLE (self-intersecting)")

