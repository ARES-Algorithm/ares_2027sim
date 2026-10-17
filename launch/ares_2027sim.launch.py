"""Launch the field and BR in ROS 2 Humble / Gazebo Fortress."""

import importlib.util
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    AppendEnvironmentVariable, DeclareLaunchArgument, ExecuteProcess,
    OpaqueFunction, Shutdown,
)
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def launch_setup(context):
    share = Path(get_package_share_directory('ares_2027sim'))
    headless = LaunchConfiguration('headless').perform(context).lower() == 'true'
    paused = LaunchConfiguration('paused').perform(context).lower() == 'true'
    args = ['-v', LaunchConfiguration('verbosity').perform(context)]
    if not paused:
        args.append('-r')
    if headless:
        args.append('-s')
    args.append(str(share / 'worlds' / 'robocon_2027.sdf'))
    # Run directly: Humble's included launch wraps this in a shell, which can
    # leave an orphaned server after Ctrl+C and confuse the next spawn request.
    actions = [ExecuteProcess(
        cmd=['ign', 'gazebo', *args], output='screen', on_exit=Shutdown(),
    )]
    bridge_args = ['/clock@rosgraph_msgs/msg/Clock[ignition.msgs.Clock']
    remappings = []
    if LaunchConfiguration('spawn_br').perform(context).lower() == 'true':
        spec = importlib.util.spec_from_file_location('prepare_br', share / 'scripts' / 'prepare_br.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        description = module.prepare_robot(share / 'ares_br_urdf' / 'br.urdf')
        actions.append(Node(
            package='robot_state_publisher', executable='robot_state_publisher',
            parameters=[{'robot_description': description, 'use_sim_time': True}],
            output='screen',
        ))
        actions.append(Node(
            package='ros_gz_sim', executable='create', output='screen',
            arguments=['-world', 'robocon_2027', '-name', 'br',
                       '-topic', '/robot_description', '-allow_renaming', 'false',
                       '-x', LaunchConfiguration('br_x').perform(context),
                       '-y', LaunchConfiguration('br_y').perform(context),
                       '-z', LaunchConfiguration('br_z').perform(context),
                       '-Y', LaunchConfiguration('br_yaw').perform(context)],
        ))
        bridge_args.append('/model/br/joint_state@sensor_msgs/msg/JointState[ignition.msgs.Model')
        remappings.append(('/model/br/joint_state', '/joint_states'))
        for index in range(1, 33):
            name = f'joint{index}'
            command = 'vel' if name in module.WHEEL_JOINTS else 'pos'
            topic = f'/model/br/{name}/cmd_{command}'
            bridge_args.append(f'{topic}@std_msgs/msg/Float64]ignition.msgs.Double')
            remappings.append((topic, f'/br/{name}/cmd_{command}'))
    actions.append(Node(
        package='ros_gz_bridge', executable='parameter_bridge',
        arguments=bridge_args, remappings=remappings,
        parameters=[{'use_sim_time': True}], output='screen',
    ))
    return actions


def generate_launch_description():
    share = Path(get_package_share_directory('ares_2027sim'))
    declarations = {
        'verbosity': '3', 'headless': 'false', 'paused': 'false', 'spawn_br': 'true',
        # Red inner start center: (-4.35, -5.10). The chassis center in CAD
        # coordinates is (-0.2968, 0.292); at yaw +pi/2 its offset is
        # (-0.292, -0.2968). Compensate so the chassis, not the CAD origin,
        # is centered in the zone.
        'br_x': '-4.058', 'br_y': '-4.8032', 'br_z': '0.16',
        'br_yaw': '1.5707963267948966',
    }
    return LaunchDescription([
        AppendEnvironmentVariable('IGN_GAZEBO_RESOURCE_PATH', str(share.parent)),
        *[DeclareLaunchArgument(name, default_value=value) for name, value in declarations.items()],
        OpaqueFunction(function=launch_setup),
    ])
