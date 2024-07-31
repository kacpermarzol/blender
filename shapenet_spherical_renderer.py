import argparse
import numpy as np
import os
import sys
sys.path.append(os.path.dirname(__file__))

import util
import blender_interface

p = argparse.ArgumentParser(description='Renders given obj file by rotation a camera around it.')
p.add_argument('--mesh_fpath', type=str, required=True, help='The path the output will be dumped to.')
p.add_argument('--output_dir', type=str, required=True, help='The path the output will be dumped to.')
p.add_argument('--num_observations', type=int, required=True, help='The number of observations to render.')
p.add_argument('--sphere_radius', type=float, required=True, help='The radius of the sphere around which the camera will rotate.')
p.add_argument('--mode', type=str, required=True, help='Options: train or test')

argv = sys.argv
argv = sys.argv[sys.argv.index("--") + 1:]

opt = p.parse_args(argv)

instance_name = opt.mesh_fpath.split('/')[-1].split('.')[0]
instance_dir = os.path.join(opt.output_dir, instance_name)

renderer = blender_interface.BlenderInterface(resolution=128)

if opt.mode == 'train':
    cam_locations = util.sample_spherical(opt.num_observations, opt.sphere_radius)
elif opt.mode == 'test':
    cam_locations = util.get_archimedean_spiral(opt.sphere_radius, opt.num_observations)
elif opt.mode == 'ssdnerf':
    cam_locations = [[1.3, 0.0, 0.0], [-1.3, 0.0, 0.0], [0.0, 0.0, 1.3],
                 [0.0, 0.0, -1.3], [0.5, 1.09087, 0.5], [-0.5, 1.09087, -0.5]]

    # directory = '/Users/kacpermarzol/PycharmProjects/blender/shapenet2/02958343/pose'
    #
    # files = [f for f in os.listdir(directory) if f.endswith('.txt')]
    # files.sort(key=lambda x: int(x.split('.')[0]))
    # cam_locations = []
    # for filename in files[:10]:
    #     file_path = os.path.join(directory, filename)
    #     with open(file_path, 'r') as file:
    #         print("FILE ", file_path)
    #         lines = file.read().split()
    #         floats = []
    #         for item in lines:
    #             try:
    #                 num = float(item)
    #                 floats.append(num)
    #             except ValueError:
    #                 continue
    #         first_three_floats = [floats[7], floats[11], floats[3]]
    #         cam_locations.append(first_three_floats)

obj_location = np.zeros((1,3))

cv_poses = util.look_at(cam_locations, obj_location)
blender_poses = [util.cv_cam2world_to_bcam2world(m) for m in cv_poses]


shapenet_rotation_mat = np.array([[1.0000000e+00,  0.0000000e+00,  0.0000000e+00],
                                  [0.0000000e+00, -1.0000000e+00, -1.2246468e-16],
                                  [0.0000000e+00,  1.2246468e-16, -1.0000000e+00]])
rot_mat = np.eye(3)
hom_coords = np.array([[0., 0., 0., 1.]]).reshape(1, 4)
obj_pose = np.concatenate((rot_mat, obj_location.reshape(3,1)), axis=-1)
obj_pose = np.concatenate((obj_pose, hom_coords), axis=0)


renderer.import_mesh(opt.mesh_fpath, scale=1., object_world_matrix=obj_pose)
renderer.render(instance_dir, blender_poses, write_cam_params=True)