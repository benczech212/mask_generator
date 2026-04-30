import os
from mask_processor import get_scene_hierarchy

session_dir = 'temp_uploads/cdb176b3-fe7e-4314-a10c-5796001e6ee0'
filepath = os.path.join(session_dir, 'Octagon_Full.step')

hierarchy = get_scene_hierarchy(filepath)
import json
print(json.dumps(hierarchy, indent=2))
