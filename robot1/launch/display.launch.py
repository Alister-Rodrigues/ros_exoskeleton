from launch import LaunchDescription
from launch_ros.actions import Node
from launch.substitutions import Command
from launch_ros.parameter_descriptions import ParameterValue
from ament_index_python.packages import get_package_share_directory
import os

def generate_launch_description():
    package_path = get_package_share_directory('robot1')

    xacro_file = os.path.join(
        package_path, 
        'urdf',
        "exoskeleton.urdf.xacro"
    )

    robot_description = ParameterValue(
        Command(["xacro", " ", xacro_file]),
        value_type=str
    )

    return LaunchDescription([
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            parameters=[
                {
                    "robot_description": robot_description
                }
            ]
        ),
        # Node(
        #     package='joint_state_publisher_gui',
        #     executable='joint_state_publisher_gui'
        # ),
        Node(
            package="rviz2",
            executable='rviz2',
            arguments=[
                "-d",
                os.path.join(package_path, 'rviz', 'exoskeleton.rviz')
            ]
        )
    ])
