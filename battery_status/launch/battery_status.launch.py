from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package='battery_status',
            executable='battery_status_node',
            name='battery_status_node',
            output='screen',
            parameters=[{
                'publish_rate_hz': 1.0,
                'use_serial': False,           # set True when ESP32 is connected
                'serial_port': '/dev/ttyACM0',
                'baud_rate': 115200,
            }]
        )
    ])
