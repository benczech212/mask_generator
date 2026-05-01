import xml.etree.ElementTree as ET

tree = ET.parse('/home/benczech/dev/mask_generator/test_outputs/Test Layout.xml')
tmpl_slice = tree.find('.//Slice')
print("Slice found:", tmpl_slice is not None)
if tmpl_slice is not None:
    pm = tmpl_slice.find('.//Warper/Params[@name="Warper"]/ParamChoice[@name="Point Mode"]')
    print("Point Mode:", pm.get('value'))
    bw = tmpl_slice.find('.//Warper/BezierWarper/vertices')
    print("Bezier vertices:", len(bw.findall('v')))
    
