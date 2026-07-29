import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    # ── Launch Arguments ────────────────────────────────────────────────────────
    serial_port_arg = DeclareLaunchArgument(
        'serial_port',
        default_value='/dev/ttyUSB0',
        description='Serial port for ESP32 UART communication'
    )
    baud_rate_arg = DeclareLaunchArgument(
        'baud_rate',
        default_value='115200',
        description='Baud rate for serial communication'
    )
    use_serial_arg = DeclareLaunchArgument(
        'use_serial',
        default_value='True',
        description='Set True when ESP32 hardware is connected for battery monitoring'
    )
    launch_rviz_arg = DeclareLaunchArgument(
        'launch_rviz',
        default_value='True',
        description='Launch RViz 2 3D exoskeleton model visualization'
    )

    serial_port = LaunchConfiguration('serial_port')
    baud_rate = LaunchConfiguration('baud_rate')
    use_serial = LaunchConfiguration('use_serial')
    launch_rviz = LaunchConfiguration('launch_rviz')

    # ── 1. PyQt6 Dashboard & Controller Node ────────────────────────────────────
    dashboard_node = Node(
        package='dashboard',
        executable='pyqt6_node',
        name='pyqt6_dashboard',
        output='screen'
    )

    # 2. Battery Status Telemetry Node ────────────────────────────────────────
    battery_status_node = Node(
        package='battery_status',
        executable='battery_status_node',
        name='battery_status_node',
        output='screen',
        parameters=[{
            'publish_rate_hz': 1.0,
            'use_serial': use_serial,
            'serial_port': serial_port,
            'baud_rate': baud_rate,
        }]
    )

    # 3. Serial Bridge Node (UART to ESP32 Hardware) ──────────────────────────
    serial_bridge_node = Node(
        package='motor_control',
        executable='serial_bridge',
        name='serial_bridge_node',
        output='screen',
        parameters=[{
            'serial_port': serial_port,
            'baud_rate': baud_rate,
        }]
    )

    # 4. Robot 3D Visualization (RViz + Robot State Publisher) ────────────────
    robot1_share = get_package_share_directory('robot1')
    rviz_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(robot1_share, 'launch', 'display.launch.py')
        ),
        condition=IfCondition(launch_rviz)
    )

    return LaunchDescription([
        serial_port_arg,
        baud_rate_arg,
        use_serial_arg,
        launch_rviz_arg,
        dashboard_node,
        battery_status_node,
        serial_bridge_node,
        rviz_launch,
    ])
