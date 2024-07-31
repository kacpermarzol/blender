import os
import bpy
import util

class BlenderInterface():
    def __init__(self, resolution=128, background_color=(1, 1, 1, 1)):
        self.resolution = resolution

        # Delete the default cube (default selected)
        bpy.ops.object.delete()

        # Deselect all. All new object added to the scene will automatically selected.
        self.blender_renderer = bpy.context.scene.render
        #self.blender_renderer.use_antialiasing = False
        self.blender_renderer.resolution_x = resolution
        self.blender_renderer.resolution_y = resolution
        self.blender_renderer.resolution_percentage = 100
        self.blender_renderer.image_settings.file_format = 'PNG'  # set output format to .png

        # Ensure there is a World in the scene
        if not bpy.context.scene.world:
            bpy.context.scene.world = bpy.data.worlds.new("World")

        world = bpy.context.scene.world

        # Enable use_nodes for the world
        world.use_nodes = True

        # Get the node tree of the world
        node_tree = world.node_tree

        # Clear existing nodes
        nodes = node_tree.nodes
        nodes.clear()

        # Add Background node
        bg_node = nodes.new(type='ShaderNodeBackground')
        bg_node.inputs['Color'].default_value = background_color
        bg_node.inputs['Strength'].default_value = 1.0

        # Add World Output node
        output_node = nodes.new(type='ShaderNodeOutputWorld')

        # Link nodes
        links = node_tree.links
        links.new(bg_node.outputs['Background'], output_node.inputs['Surface'])

        # Remove existing lights
        bpy.ops.object.select_by_type(type='LIGHT')
        bpy.ops.object.delete(use_global=False)

        # Create a main sun lamp for directional light
        bpy.ops.object.light_add(type='SUN', location=(1.3, 1.3, 0.0))
        lamp1 = bpy.context.object.data
        lamp1.use_shadow = True
        lamp1.specular_factor = 0.5
        lamp1.energy = 3

        bpy.context.object.rotation_euler = (0.785, 0.0, 0)  # Rotate for directional light

        # Create a fill light (area) to soften shadows and give overall illumination
        bpy.ops.object.light_add(type='AREA', location=(1.3, 1.3, 1.3))
        lamp2 = bpy.context.object.data
        lamp2.shape = 'RECTANGLE'
        lamp2.size = 10
        lamp2.size_y = 10
        lamp2.use_shadow = False
        lamp2.energy = 0.5
        bpy.context.object.rotation_euler = (0.785, 0.785, 0)  # Rotate for fill light

        # Set the world background to pure white
        bpy.context.scene.world.use_nodes = True
        world_nodes = bpy.context.scene.world.node_tree.nodes
        world_links = bpy.context.scene.world.node_tree.links

        # Remove existing nodes
        for node in world_nodes:
            world_nodes.remove(node)

        # Add a background node
        bg_node = world_nodes.new(type='ShaderNodeBackground')
        bg_node.inputs['Color'].default_value = (1, 1, 1, 1)  # White background
        bg_node.inputs['Strength'].default_value = 1.0

        # Add a world output node
        world_output = world_nodes.new(type='ShaderNodeOutputWorld')

        # Link the background node to the world output
        world_links.new(bg_node.outputs['Background'], world_output.inputs['Surface'])

        # Ensure the objects are lit properly
        bpy.context.view_layer.update()

        # Set up the camera
        self.camera = bpy.context.scene.camera
        self.camera.data.sensor_height = self.camera.data.sensor_width # Square sensor
        util.set_camera_focal_length_in_world_units(self.camera.data, 525./512*resolution) # Set focal length to a common value (kinect)

        bpy.ops.object.select_all(action='DESELECT')

    def import_mesh(self, fpath, scale=1., object_world_matrix=None):
        ext = os.path.splitext(fpath)[-1]
        if ext == '.obj':
            # bpy.ops.import_scene.obj(filepath=str(fpath))
            bpy.ops.wm.obj_import(filepath=str(fpath))
        elif ext == '.ply':
            bpy.ops.import_mesh.ply(filepath=str(fpath))
        elif ext == ".gltf":
            bpy.ops.import_scene.gltf(filepath=str(fpath))

        obj = bpy.context.selected_objects[0]
        # Correct orientation for GLTF

        import math



        # if object_world_matrix is not None:
        #     obj.matrix_world = object_world_matrix

        bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
        obj.location = (0., 0., 0.) # center the bounding box!

        if scale != 1.:
            bpy.ops.transform.resize(value=(scale, scale, scale))

        bpy.ops.transform.rotate(value=math.radians(-270) ,orient_axis="X")
        bpy.ops.transform.rotate(value=math.radians(90) ,orient_axis="Y")


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
            img_dir = os.path.join(output_dir, 'rgb')
            pose_dir = os.path.join(output_dir, 'pose')

            util.cond_mkdir(img_dir)
            util.cond_mkdir(pose_dir)
        else:
            img_dir = output_dir
            util.cond_mkdir(img_dir)

        if write_cam_params:
            K = util.get_calibration_matrix_K_from_blender(self.camera.data)
            with open(os.path.join(output_dir, 'intrinsics.txt'),'w') as intrinsics_file:
                intrinsics_file.write('%f %f %f 0.\n'%(K[0][0], K[0][2], K[1][2]))
                intrinsics_file.write('0. 0. 0.\n')
                intrinsics_file.write('1.\n')
                intrinsics_file.write('%d %d\n'%(self.resolution, self.resolution))

        for i in range(len(blender_cam2world_matrices)):
            self.camera.matrix_world = blender_cam2world_matrices[i]

            # Render the object
            if os.path.exists(os.path.join(img_dir, '%06d.png' % i)):
                continue

            # Render the color image
            self.blender_renderer.filepath = os.path.join(img_dir, '%06d.png'%i)
            bpy.ops.render.render(write_still=True)

            if write_cam_params:
                # Write out camera pose
                RT = util.get_world2cam_from_blender_cam(self.camera)
                cam2world = RT.inverted()
                with open(os.path.join(pose_dir, '%06d.txt'%i),'w') as pose_file:
                    matrix_flat = []
                    for j in range(4):
                        for k in range(4):
                            matrix_flat.append(cam2world[j][k])
                    pose_file.write(' '.join(map(str, matrix_flat)) + '\n')

        # Remember which meshes were just imported
        meshes_to_remove = []
        for ob in bpy.context.selected_objects:
            meshes_to_remove.append(ob.data)

        bpy.ops.object.delete()

        # Remove the meshes from memory too
        for mesh in meshes_to_remove:
            bpy.data.meshes.remove(mesh)