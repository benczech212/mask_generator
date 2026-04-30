import xml.etree.ElementTree as ET
import matplotlib.pyplot as plt

tree = ET.parse('test_outputs/Octagon_Full_masks (2)/Octagon_Full_resolume_layout.xml')
root = tree.getroot()

for poly in root.findall('.//Polygon'):
    layer = poly.find('.//Param[@name="Name"]').get('value')
    if layer == "Beams_0":
        for contour in poly.findall('.//InputContour'):
            pts = contour.find('points')
            if pts is not None:
                xs, ys = [], []
                for v in pts.findall('v'):
                    xs.append(float(v.get('x')))
                    ys.append(float(v.get('y')))
                if len(xs) > 0:
                    xs.append(xs[0])
                    ys.append(ys[0])
                    plt.figure()
                    plt.plot(xs, ys, marker='o', markersize=2)
                    plt.title(f"InputContour {layer}")
                    plt.savefig('scratch/Beams_0_Input.png')
                    plt.close()
                    
        for contour in poly.findall('.//OutputContour'):
            pts = contour.find('points')
            if pts is not None:
                xs, ys = [], []
                for v in pts.findall('v'):
                    xs.append(float(v.get('x')))
                    ys.append(float(v.get('y')))
                if len(xs) > 0:
                    xs.append(xs[0])
                    ys.append(ys[0])
                    plt.figure()
                    plt.plot(xs, ys, marker='o', markersize=2)
                    plt.title(f"OutputContour {layer}")
                    plt.savefig('scratch/Beams_0_Output.png')
                    plt.close()
