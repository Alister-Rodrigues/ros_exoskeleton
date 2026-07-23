from launch import LaunchDescription
from launch.actions import ExecuteProcess


def generate_launch_description():
    return LaunchDescription([
        ExecuteProcess(
            cmd=['ros2', 'run', 'dashboard', 'pyqt6_node'],
            output='screen'
        ),
        ExecuteProcess(
            cmd=['ros2', 'run', 'exoskeleton_control', 'motor'],
            output='screen'
        )
    ])
