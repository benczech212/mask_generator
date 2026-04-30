import lxml.etree as ET
from copy import deepcopy

tree = ET.parse('Test Layout.xml')
root = tree.getroot()

screens = root.xpath('//screens/Screen')
if not screens:
    print("NO SCREENS")
else:
    screen = screens[0]
    layers = screen.find('layers')
    
    # get a template polygon
    tmpl_poly = layers.find('Polygon')
    
    layers.clear()
    
    # We can just copy the template polygon and modify its points, rects, and name!
    new_poly = deepcopy(tmpl_poly)
    params = new_poly.find('.//Params[@name="Common"]')
    for param in params.findall('Param'):
        if param.get('name') == 'Name':
            param.set('value', 'My Fixed Name!!')
            print("Set name")
            
    # And clear the points and add ours
    in_pts = new_poly.find('.//InputContour/points')
    in_pts.clear()
    
    layers.append(new_poly)

tree.write('test_modified.xml', pretty_print=True)
