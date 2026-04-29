import trimesh
import numpy as np

def test():
    scene = trimesh.load('Octagon Full.obj', process=False)
    if not isinstance(scene, trimesh.Scene):
        s = trimesh.Scene()
        s.add_geometry(scene)
        scene = s
        
    print("Initial transform:")
    print(scene.camera_transform)
    
    # We won't actually call show() here because it will block the automated terminal
    # But we can inspect the properties.
    transform = scene.camera_transform
    camera_pos = transform[:3, 3]
    forward = -transform[:3, 2]
    up = transform[:3, 1]
    
    print("Derived pos:", camera_pos)
    print("Derived target:", camera_pos + forward)
    print("Derived up:", up)

test()
