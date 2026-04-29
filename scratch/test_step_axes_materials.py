import re
import sys

def analyze_step_file(filepath):
    print(f"Analyzing {filepath}...")
    try:
        with open(filepath, 'r') as f:
            content = f.read()
            
        # Find all AXIS2_PLACEMENT_3D
        # Format: #ID = AXIS2_PLACEMENT_3D('Name', #Location, #Z_Axis, #X_Axis);
        axis_pattern = re.compile(r"#(\d+)\s*=\s*AXIS2_PLACEMENT_3D\s*\(([^)]+)\)\s*;", re.IGNORECASE)
        axes = axis_pattern.findall(content)
        
        print(f"\n--- Axes (AXIS2_PLACEMENT_3D) ---")
        print(f"Total found: {len(axes)}")
        if axes:
            print("First 5 axes found:")
            for axis in axes[:5]:
                print(f"  ID: #{axis[0]}, Args: {axis[1]}")
                
        # Find Materials
        # Format: #ID = REPRESENTATION('material name', (#......), #...);
        # or #ID = PROPERTY_DEFINITION('material property', 'material name', #...);
        material_rep_pattern = re.compile(r"#(\d+)\s*=\s*REPRESENTATION\s*\(\s*'material name'\s*,\s*\(([^)]+)\)\s*,\s*#(\d+)\s*\)\s*;", re.IGNORECASE)
        material_reps = material_rep_pattern.findall(content)
        
        material_prop_pattern = re.compile(r"#(\d+)\s*=\s*PROPERTY_DEFINITION\s*\(\s*'material property'\s*,\s*'([^']+)'\s*,\s*#(\d+)\s*\)\s*;", re.IGNORECASE)
        material_props = material_prop_pattern.findall(content)
        
        print(f"\n--- Materials ---")
        print(f"Total material representations found: {len(material_reps)}")
        for rep in material_reps:
            print(f"  ID: #{rep[0]}, Entities: {rep[1]}, Context: #{rep[2]}")
            
        print(f"Total material properties found: {len(material_props)}")
        for prop in material_props:
            print(f"  ID: #{prop[0]}, Name: '{prop[1]}', Definition: #{prop[2]}")

        # Also look for colors (SURFACE_STYLE_USAGE or PRESENTATION_STYLE_ASSIGNMENT)
        color_pattern = re.compile(r"#(\d+)\s*=\s*COLOUR_RGB\s*\(\s*'([^']*)'\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*\)\s*;", re.IGNORECASE)
        colors = color_pattern.findall(content)
        print(f"\n--- Colors (COLOUR_RGB) ---")
        print(f"Total colors found: {len(colors)}")
        for color in colors[:5]:
            print(f"  ID: #{color[0]}, Name: '{color[1]}', RGB: ({color[2]}, {color[3]}, {color[4]})")

    except FileNotFoundError:
        print(f"Error: File {filepath} not found.")

if __name__ == "__main__":
    filepath = sys.argv[1] if len(sys.argv) > 1 else "Octagon Full.step"
    analyze_step_file(filepath)
