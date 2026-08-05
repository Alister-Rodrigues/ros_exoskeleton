from launch import LaunchDescription
from launch.actions import ExecuteProcess


def generate_launch_description():
    return LaunchDescription([
        ExecuteProcess(
            cmd=[
                'ros2', 'run', 'motor_control', 'serial_bridge',
                '--ros-args',
                '-p', 'serial_port:=/dev/ttyACM0',
                '-p', 'baud_rate:=115200',
            ],
            output='screen'
        )
    ])
