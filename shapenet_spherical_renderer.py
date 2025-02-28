import numpy as np
import os
import util
import blender_interface
import shutil
import math

from PIL import Image
def white_background(folder_path):
    if not os.path.isdir(folder_path):
        raise ValueError("not a dir")
    for file_name in os.listdir(folder_path):
        file_path = os.path.join(folder_path, file_name)

        if file_name.lower().endswith(('.png', '.jpg', '.jpeg')):
            try:
                img = Image.open(file_path).convert("RGBA")
                white = Image.new("RGBA", img.size, (255, 255, 255, 255))
                composed_img = Image.alpha_composite(white, img)
                composed_img = composed_img.convert("RGB")
                composed_img.save(file_path)
            except Exception as e:
                print(f"Failed to process {file_name}: {e}")

def prepare_for_render(obj_location, cam_locations):
    cv_poses = util.look_at(cam_locations, obj_location)
    blender_poses = [util.cv_cam2world_to_bcam2world(m) for m in cv_poses]
    rot_mat = np.eye(3)
    hom_coords = np.array([[0., 0., 0., 1.]]).reshape(1, 4)
    obj_pose = np.concatenate((rot_mat, obj_location.reshape(3, 1)), axis=-1)
    obj_pose = np.concatenate((obj_pose, hom_coords), axis=0)
    return obj_pose, blender_poses

def render_dataset(srn_path, mode, percent=1):
    all_scenes = os.listdir(srn_path)
    x_percent = math.ceil(len(all_scenes) * percent)
    models_path = f'shapenet-gltf/car'  # pliki gltf z shapnet

    for scene in all_scenes[:x_percent]:
        gltf_path = models_path + f'/{scene}.gltf'
        scene_path = f'shapenet2/cars_{mode}/' + scene

        os.makedirs(scene_path, exist_ok=True)
        srn_scene_path = os.path.join(srn_path, scene)
        print(srn_scene_path)

        pose = os.path.join(srn_scene_path, "pose")
        intrinsics = os.path.join(srn_scene_path, "intrinsics.txt")

        shutil.copy(intrinsics, scene_path)
        shutil.copytree(pose, scene_path+'/pose', dirs_exist_ok=True)

        pose_files = [f for f in os.listdir(pose) if f.endswith('.txt')]
        pose_files.sort(key=lambda x: int(x.split('.')[0]))

        cam_locations = []

        for pose_file in pose_files:
            pose_file = os.path.join(pose, pose_file)
            with open(pose_file, 'r') as file:
                lines = file.read().split()
                vals = []
                for item in lines:
                    try:
                        num = float(item)
                        vals.append(num)
                    except ValueError:
                        continue
                xyz = [vals[7], vals[11], vals[3]]
                cam_locations.append(xyz)

        obj_location = np.zeros((1,3))

        obj_pose, blender_poses = prepare_for_render(obj_location, cam_locations)
        renderer.import_mesh(gltf_path, scale=1., object_world_matrix=obj_pose)
        renderer.render(scene_path + '/rgb', blender_poses, write_cam_params=False)
        white_background(scene_path + '/rgb')

        if mode == "train":
            planes_locations = [[-1.3, 0.0, 0.0], [1.3, 0.0, 0.0], [0.0, 0.0, -1.3],
                                [0.0, 0.0, 1.3], [-0.5, 1.09087, -0.5], [0.5, 1.09087, 0.5]]
            obj_pose, blender_poses = prepare_for_render(obj_location, planes_locations)

            renderer.import_mesh(gltf_path, scale=1., object_world_matrix=obj_pose)
            renderer.render(scene_path, blender_poses, write_cam_params=True)
            white_background(scene_path + '/rgb_multi')

if __name__ == '__main__':
    print("Rendering from main, preparation")
    renderer = blender_interface.BlenderInterface(resolution=128)

    srn = 'srn_cars' ## dataset z ssdnerfa, obrazy + pozycje + intrinsics
    train = srn + '/train'
    test = srn + '/test'
    val = srn + '/val'

    print("start rendering")
    render_dataset(train, mode="train", percent=1)
    # render_dataset(test, mode="test", percent=1)
    # render_dataset(val, mode="val", percent=1)
