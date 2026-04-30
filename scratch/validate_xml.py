import xml.etree.ElementTree as ET
import math

tree = ET.parse('test_outputs/Octagon_Full_masks (2)/Octagon_Full_resolume_layout.xml')
root = tree.getroot()

for poly in root.findall('.//Polygon'):
    layer = poly.find('.//Param[@name="Name"]').get('value')
    for io in ['InputContour', 'OutputContour']:
        for contour in poly.findall(f'.//{io}'):
            pts = contour.find('points')
            segments = contour.find('segments')
            
            if pts is not None:
                parsed_pts = []
                for v in pts.findall('v'):
                    x = float(v.get('x'))
                    y = float(v.get('y'))
                    if math.isnan(x) or math.isnan(y):
                        print(f"NaN in Layer {layer} {io}!")
                    parsed_pts.append((x, y))
                
                if segments is None:
                    print(f"Missing segments in Layer {layer} {io}!")
                elif segments.text is None:
                    print(f"Empty segments text in Layer {layer} {io}!")
                elif len(segments.text) != len(parsed_pts):
                    print(f"Mismatch in Layer {layer} {io}! Points: {len(parsed_pts)}, Segments: {len(segments.text)}")

print("Validation complete.")
