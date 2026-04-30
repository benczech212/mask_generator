import sys
sys.path.append('.')
from mask_processor import get_scene_hierarchy
filepath = "temp_uploads/3900a792-ca8d-4ab5-b005-99590d6efafe/Octagon_Full.step"
hierarchy = get_scene_hierarchy(filepath)
print(hierarchy)
