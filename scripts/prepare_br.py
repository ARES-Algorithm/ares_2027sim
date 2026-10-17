#!/usr/bin/env python3
"""Adapt the CAD URDF for an initial ROS 2 Humble / Gazebo Fortress simulation.

The source URDF stays in the submodule. Collision primitives and ideal joint
servos are provisional; they are not calibrated actuator or climbing models.
"""

import argparse
from pathlib import Path
import struct
import xml.etree.ElementTree as ET


WHEEL_JOINTS = tuple(f'joint{i}' for i in range(9, 13))


def mesh_bounds(path):
    """Read the actual vertices of a binary STL without extra dependencies."""
    data = Path(path).read_bytes()
    count, = struct.unpack_from('<I', data, 80)
    if len(data) != 84 + 50 * count or count == 0:
        raise ValueError(f'Not a valid nonempty binary STL: {path}')
    lower = [float('inf')] * 3
    upper = [-float('inf')] * 3
    for index in range(count):
        values = struct.unpack_from('<9f', data, 84 + 50 * index + 12)
        for vertex in range(3):
            for axis in range(3):
                value = values[3 * vertex + axis]
                lower[axis] = min(lower[axis], value)
                upper[axis] = max(upper[axis], value)
    return lower, upper


def add_text(parent, tag, value):
    ET.SubElement(parent, tag).text = str(value)


def prepare_robot(source, model_name='br'):
    """Return a URDF with resolved visuals, primitive collisions and servos."""
    source = Path(source).resolve()
    robot = ET.parse(source).getroot()
    robot.set('name', model_name)
    if robot.find("joint[@name='joint222']") is not None:
        raise ValueError('Remove the erroneous joint222 from the source URDF first')

    for link in robot.findall('link'):
        name = link.attrib['name']
        visual_mesh = link.find('visual/geometry/mesh')
        if visual_mesh is None:
            continue  # Fixed reference frames have no physical geometry.
        mesh_path = source.parent / visual_mesh.attrib['filename']
        lower, upper = mesh_bounds(mesh_path)
        for mesh in link.findall('visual/geometry/mesh'):
            mesh.set('filename', mesh_path.as_uri())
        for collision in link.findall('collision'):
            link.remove(collision)
        collision = ET.SubElement(link, 'collision')
        center = [(a + b) / 2 for a, b in zip(lower, upper)]
        size = [b - a for a, b in zip(lower, upper)]
        origin = ET.SubElement(collision, 'origin', xyz=' '.join(map(str, center)))
        geometry = ET.SubElement(collision, 'geometry')
        if name in ('link9', 'link10', 'link11', 'link12'):
            # Cylinders use local Z; CAD wheels rotate about local Y.
            origin.set('rpy', '1.5707963267948966 0 0')
            ET.SubElement(geometry, 'cylinder', radius=str(max(size[0], size[2]) / 2),
                          length=str(size[1]))
        else:
            ET.SubElement(geometry, 'box', size=' '.join(map(str, size)))
        gazebo = ET.SubElement(robot, 'gazebo', reference=name)
        add_text(gazebo, 'mu1', 0.8)
        add_text(gazebo, 'mu2', 0.8)

    extensions = ET.SubElement(robot, 'gazebo')
    publisher = ET.SubElement(
        extensions, 'plugin', filename='ignition-gazebo-joint-state-publisher-system',
        name='ignition::gazebo::systems::JointStatePublisher')
    add_text(publisher, 'topic', f'/model/{model_name}/joint_state')

    for joint in robot.findall('joint'):
        if joint.attrib['type'] == 'fixed':
            continue
        name = joint.attrib['name']
        # A rolling wheel must never run into the CAD export's +/-314 rad stop.
        if name in WHEEL_JOINTS:
            joint.set('type', 'continuous')
            for bound in ('lower', 'upper'):
                joint.find('limit').attrib.pop(bound, None)
        if joint.find('dynamics') is None:
            ET.SubElement(joint, 'dynamics', damping='0.1', friction='0.0')
        wheel = name in WHEEL_JOINTS
        system = 'JointController' if wheel else 'JointPositionController'
        filename = ('joint-controller' if wheel else 'joint-position-controller')
        plugin = ET.SubElement(
            extensions, 'plugin', filename=f'ignition-gazebo-{filename}-system',
            name=f'ignition::gazebo::systems::{system}')
        add_text(plugin, 'joint_name', name)
        add_text(plugin, 'topic', f'/model/{model_name}/{name}/cmd_{"vel" if wheel else "pos"}')
        if wheel:
            add_text(plugin, 'initial_velocity', 0)
        else:
            # Ideal bounded velocity servos keep the imported mechanism posed.
            # In particular, holding joint32 at zero is NOT a physical latch.
            add_text(plugin, 'initial_position', 0)
            add_text(plugin, 'use_velocity_commands', 'true')
            speed = 0.15 if joint.attrib['type'] == 'prismatic' else 1.0
            add_text(plugin, 'cmd_max', speed)
            add_text(plugin, 'cmd_min', -speed)
    ET.indent(robot, space='  ')
    return ET.tostring(robot, encoding='unicode')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(prepare_robot(args.source))


if __name__ == '__main__':
    main()
