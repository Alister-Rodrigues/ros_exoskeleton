import os
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    SetEnvironmentVariable,
)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory

# ── PYTHONPATH: inject rviz_widget shared library so the dashboard can import it ──
_RVIZ_WIDGET_LIB = (
    '/home/shijaz/Documents/exo_ws/src/rviz_widget/build/rviz_widget/'
    'build/lib.linux-x86_64-cpython-312'
)
_PYTHONPATH = ':'.join(filter(None, [_RVIZ_WIDGET_LIB, os.environ.get('PYTHONPATH', '')]))


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
        output='screen',
        additional_env={
            # ── Suppress rviz_common debug icon-not-found spam ──────────────────
            # rviz_common tries .svg then .png fallbacks for nav2 plugin icons
            # that are not installed in ROS Jazzy.  These are harmless debug
            # messages; raising the minimum severity to WARN hides them while
            # keeping genuine warnings and errors visible.
            'RCUTILS_LOGGING_MIN_SEVERITY':   'WARN',
            # ── Anti-flicker: sync OGRE buffer swaps to monitor refresh ──────
            # Mesa / AMD / Intel: force adaptive VSync (mode 3)
            'vblank_mode':                '3',
            # Mesa: use FBO for render-to-texture (more stable than pbuffer)
            'MESA_GLSL_CACHE_DISABLE':    '0',
            # NVIDIA proprietary: force VSync on
            '__GL_SYNC_TO_VBLANK':        '1',
            '__GL_YIELD':                 'USLEEP',
            # Use desktop (native) OpenGL — not ANGLE or software fallback.
            # This ensures OGRE and Qt share the same GL context path.
            'QT_OPENGL':                  'desktop',
            # Disable X11 MIT-SHM shared memory — can interfere with
            # embedded OpenGL sub-windows causing X11 BadMatch flicker.
            'QT_X11_NO_MITSHM':           '1',
        },
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
        # Set PYTHONPATH first so every spawned node inherits it
        SetEnvironmentVariable('PYTHONPATH', _PYTHONPATH),
        serial_port_arg,
        baud_rate_arg,
        use_serial_arg,
        launch_rviz_arg,
        dashboard_node,
        battery_status_node,
        serial_bridge_node,
        rviz_launch,
    ])
