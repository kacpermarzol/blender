import os
import util
import bpy


class BlenderInterface():
    def __init__(self, resolution=128, background_color=(1,1,1)):
        self.resolution = resolution

        # Delete the default cube (default selected)
        bpy.ops.object.select_all(action='DESELECT')
        bpy.data.objects['Cube'].select_set(True)
        bpy.ops.object.delete()

        # Deselect all. All new object added to the scene will automatically selected.
        self.blender_renderer = bpy.context.scene.render
        self.blender_renderer.resolution_x = resolution
        self.blender_renderer.resolution_y = resolution
        self.blender_renderer.resolution_percentage = 100
        self.blender_renderer.image_settings.file_format = 'PNG'  # set output format to .png

        bpy.context.scene.world.color = background_color

        bpy.ops.object.light_add(type='SUN')
        lamp1 = bpy.context.object
        lamp1.data.energy = 1.0

        bpy.ops.object.light_add(type='SUN')
        lamp2 = bpy.context.object
        lamp2.data.energy = 1.0
        lamp2.rotation_euler = lamp1.rotation_euler
        lamp2.rotation_euler[0] += 3.14159  # Rotate by 180 degrees

        bpy.ops.object.light_add(type='SUN')
        lamp3 = bpy.context.object
        lamp3.data.energy = 0.3
        lamp3.rotation_euler = lamp1.rotation_euler
        lamp3.rotation_euler[0] += 1.5708  # Rotate by 90 degrees

        # Set up the camera
        self.camera = bpy.context.scene.camera
        if not self.camera:
            bpy.ops.object.camera_add()
            self.camera = bpy.context.object
            bpy.context.scene.camera = self.camera

        self.camera.data.sensor_height = self.camera.data.sensor_width  # Square sensor

        # Set focal length to a common value (kinect)
        self.set_camera_focal_length_in_world_units(525. / 512 * resolution)

        bpy.ops.object.select_all(action='DESELECT')

    def set_camera_focal_length_in_world_units(self, focal_length):
        # Assuming the camera is perspective
        self.camera.data.lens = focal_length

    def import_mesh(self, fpath, scale=1., object_world_matrix=None):
        ext = os.path.splitext(fpath)[-1]
        if ext == '.obj':
            # bpy.ops.import_scene.obj(filepath=str(fpath))
            bpy.ops.wm.obj_import(filepath=str(fpath))
        elif ext == '.ply':
            bpy.ops.import_mesh.ply(filepath=str(fpath))

        obj = bpy.context.selected_objects[0]

        if object_world_matrix is not None:
            obj.matrix_world = object_world_matrix

        bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
        obj.location = (0., 0., 0.) # center the bounding box!

        if scale != 1.:
            bpy.ops.transform.resize(value=(scale, scale, scale))

        # Disable transparency & specularities
        for mat in bpy.data.materials:
            mat.blend_method = 'OPAQUE'
            mat.specular_intensity = 0.0

        # Disable texture interpolation
        for tex in bpy.data.textures:
            try:
                tex.use_interpolation = False
                tex.use_mipmap = False
                tex.filter_type = 'BOX'
            except AttributeError:
                continue

    def render(self, output_dir, blender_cam2world_matrices, write_cam_params=False):
        x = os.makedirs(output_dir, exist_ok=True)
        img_dir = os.path.join(output_dir, 'rgb') if write_cam_params else output_dir
        pose_dir = os.path.join(output_dir, 'pose') if write_cam_params else None

        if write_cam_params:
            os.makedirs(img_dir, exist_ok=True)
            os.makedirs(pose_dir, exist_ok=True)
            K = self.get_calibration_matrix_K_from_blender(self.camera.data)
            with open(os.path.join(output_dir, 'intrinsics.txt'), 'w') as intrinsics_file:
                intrinsics_file.write('%f %f %f 0.\n' % (K[0][0], K[0][2], K[1][2]))
                intrinsics_file.write('0. 0. 0.\n')
                intrinsics_file.write('1.\n')
                intrinsics_file.write('%d %d\n'%(self.resolution, self.resolution))

        for i, matrix in enumerate(blender_cam2world_matrices):
            self.camera.matrix_world = matrix

            # Render the object
            if os.path.exists(os.path.join(img_dir, '%06d.png' % i)):
                continue

            # Render the color image
            self.blender_renderer.filepath = os.path.join(img_dir, '%06d.png'%i)
            bpy.ops.render.render(write_still=True)

            if write_cam_params:
                # Write out camera pose
                RT = self.get_world2cam_from_blender_cam(self.camera)
                cam2world = RT.inverted()
                with open(os.path.join(pose_dir, '%06d.txt' % i), 'w') as pose_file:
                    matrix_flat = [elem for row in cam2world for elem in row]
                    pose_file.write(' '.join(map(str, matrix_flat)) + '\n')

        # Remember which meshes were just imported
        meshes_to_remove = [ob.data for ob in bpy.context.selected_objects]
        bpy.ops.object.delete()

        # Remove the meshes from memory too
        for mesh in meshes_to_remove:
            bpy.data.meshes.remove(mesh)

    def get_calibration_matrix_K_from_blender(self, camdata):
        f_in_mm = camdata.lens
        resolution_x_in_px = self.resolution
        resolution_y_in_px = self.resolution
        scale = resolution_x_in_px / resolution_x_in_px

        sensor_width_in_mm = camdata.sensor_width
        sensor_height_in_mm = camdata.sensor_height

        if camdata.sensor_fit == 'VERTICAL':
            sensor_width_in_mm = sensor_height_in_mm * resolution_x_in_px / resolution_y_in_px

        pixel_aspect_ratio = resolution_x_in_px / resolution_y_in_px

        K = [[f_in_mm * resolution_x_in_px / sensor_width_in_mm, 0, resolution_x_in_px / 2],
             [0, f_in_mm * resolution_y_in_px / (sensor_height_in_mm * pixel_aspect_ratio), resolution_y_in_px / 2],
             [0, 0, 1]]

        return K

    def get_world2cam_from_blender_cam(self, cam):
        cam = bpy.context.scene.camera
        location, rotation = cam.matrix_world.decompose()[0:2]
        RT = (rotation.to_matrix().to_4x4()).transposed()
        RT[0][3] = -location[0]
        RT[1][3] = -location[1]
        RT[2][3] = -location[2]

        return RT
