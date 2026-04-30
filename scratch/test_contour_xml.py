import lxml.etree as ET

root = ET.Element("XmlState", name="Test Layout")
ET.SubElement(root, "versionInfo", name="Resolume Arena", majorVersion="7", minorVersion="23", microVersion="2", revision="51094")
screen_setup = ET.SubElement(root, "ScreenSetup", name="ScreenSetup")
ET.SubElement(screen_setup, "CurrentCompositionTextureSize", width="1920", height="1080")
screens = ET.SubElement(screen_setup, "screens")
screen = ET.SubElement(screens, "Screen", name="Screen 1", uniqueId="1001")
layers = ET.SubElement(screen, "layers")

# Polygon addition
polygon = ET.SubElement(layers, "Polygon", uniqueId="123", IsVirgin="1")
inp = ET.SubElement(polygon, "InputContour", closed="1")
pts = ET.SubElement(inp, "points")
ET.SubElement(pts, "v", x="535.1", y="102.2")
ET.SubElement(inp, "segments").text = "L" * 1

tree = ET.ElementTree(root)
tree.write("test_out.xml", pretty_print=True, xml_declaration=True, encoding="utf-8")
