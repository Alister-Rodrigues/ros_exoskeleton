import math
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import String, Int32, Bool
from exoskeleton_interfaces.msg import MotorAngles, BatteryStatus


class JointStateNode(Node):
    def __init__(self):
        super().__init__("joint_state_node")
        self.current_angles = {
            "left_hip_joint": 0,
            "left_knee_joint": 0,
            "right_hip_joint": 0,
            "right_knee_joint": 0,
        }
        self.poses = {

            "stand_neutral":
            {
                "left_hip_joint": 0.0,
                "left_knee_joint": 0.0,
                "right_hip_joint": 0.0,
                "right_knee_joint": 0.0
            },

            "knee_bend":
            {
                "left_hip_joint": 0.26,
                "left_knee_joint": -0.52,
                "right_hip_joint": 0.26,
                "right_knee_joint": -0.52
            },

            "sitting":
            {
                "left_hip_joint": 1.40,
                "left_knee_joint": -1.30,
                "right_hip_joint": 1.40,
                "right_knee_joint": -1.30
            },

            "forward_lean":
            {
                "left_hip_joint": 0.52,
                "left_knee_joint": -0.15,
                "right_hip_joint": 0.52,
                "right_knee_joint": -0.15
            },

            "backward_lean":
            {
                "left_hip_joint": -0.35,
                "left_knee_joint": -0.09,
                "right_hip_joint": -0.35,
                "right_knee_joint": -0.09
            },

            "step_prepare_left":
            {
                "left_hip_joint": 0.45,
                "left_knee_joint": -0.70,
                "right_hip_joint": 0.0,
                "right_knee_joint": 0.0
            },

            "step_prepare_right":
            {
                "left_hip_joint": 0.0,
                "left_knee_joint": 0.0,
                "right_hip_joint": 0.45,
                "right_knee_joint": -0.70
            },

            "sit_like_bend":
            {
                "left_hip_joint": 1.40,
                "left_knee_joint": -1.30,
                "right_hip_joint": 1.40,
                "right_knee_joint": -1.30
            },

            "step_prepare":
            {
                "left_hip_joint": 0.45,
                "left_knee_joint": -0.70,
                "right_hip_joint": 0.0,
                "right_knee_joint": 0.0
            }

        }

        self.gaits = {
            "stand_neutral": [
                "stand_neutral",
            ],

            "knee_bend": [
                # "stand_neutral",
                "knee_bend",
                "stand_neutral",
            ],

            "sit_like_bend": [
                # "stand_neutral",
                "sitting",
                "stand_neutral",
            ],

            "forward_lean": [
                # "stand_neutral",
                "forward_lean",
                "stand_neutral",
            ],

            "backward_lean": [
                # "stand_neutral",
                "backward_lean",
                "stand_neutral",
            ],

            "step_prepare": [
                # "stand_neutral",
                "step_prepare_left",
                "stand_neutral",
                "step_prepare_right",
                "stand_neutral",
            ]
        }
        self.current_gait = []
        self.current_step = 0
        self.current_repeat = 0
        self.total_repeats = 0
        self.hold_time = 2.0
        self.running = False

        self.hold_timer = None
        self.holding = False

        # pubsubs
        self.publisher = self.create_publisher(
            JointState, "joint_states", 10
        )
        self.subscriber = self.create_subscription(
            JointState, "joint_states", self.listener_callback, 10
        )
        self.motor_pub = self.create_publisher(
            MotorAngles, 'motor_commands', 10
        )
        self.motor_sub = self.create_subscription(
            MotorAngles, 'motor_feedback', self.motor_feedback, 10
        )
        # Publisher for reset command → serial_bridge_node
        self.reset_pub = self.create_publisher(String, '/motor_reset', 10)
        self.speed_pub = self.create_publisher(Int32, '/motor_speed', 10)

        # Battery status subscriber
        self.battery_sub = self.create_subscription(
            BatteryStatus, '/battery_status', self.battery_callback, 10
        )
        self.conn_sub = self.create_subscription(
            Bool, '/esp32_connected', self.conn_callback, 10
        )

    def publish_joint_state(self, left_hip, left_knee, right_hip, right_knee):
        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()

        msg.name = [
            "left_hip_joint",
            "left_knee_joint",
            "right_hip_joint",
            "right_knee_joint",
        ]

        msg.position = [
            math.radians(left_hip),
            math.radians(left_knee),
            math.radians(right_hip),
            math.radians(right_knee)
        ]

        self.publisher.publish(msg)
    
    def listener_callback(self, msg):
        angles = {}
        for name, pos in zip(msg.name, msg.position):
            angles[name] = math.degrees(pos)

        if hasattr(self, 'gui'):
            self.gui.on_joint_state(
                angles["left_hip_joint"],
                angles["left_knee_joint"],
                angles["right_hip_joint"],
                angles["right_knee_joint"],
            )
    
    def publish_motor_angles(self, left_hip, left_knee, right_hip, right_knee):
        msg = MotorAngles()

        msg.left_hip = float(left_hip)
        msg.left_knee = float(left_knee)
        msg.right_hip = float(right_hip)
        msg.right_knee = float(right_knee)

        self.motor_pub.publish(msg)

    def publish_reset_motors(self):
        """Publish 'reset_motors' string on /motor_reset so serial_bridge_node
        forwards it to the ESP32 over serial."""
        msg = String()
        msg.data = 'reset_motors'
        self.reset_pub.publish(msg)
        self.get_logger().info('[JointStateNode] reset_motors published on /motor_reset')
    
    def publish_motor_speed(self, speed):
        """Publish speed value on /motor_speed so serial_bridge_node
        forwards it to the ESP32 over serial."""
        msg = Int32()
        msg.data = int(speed)
        self.speed_pub.publish(msg)
        self.get_logger().info(f'[JointStateNode] Speed {speed}% published on /motor_speed')
    
    def battery_callback(self, msg):
        """Forward battery data to the GUI."""
        if hasattr(self, 'gui'):
            self.gui.on_battery_update(msg.percentage, msg.voltage)

    def conn_callback(self, msg):
        if hasattr(self, 'gui'):
            self.gui.on_connection_update(msg.data)

    def motor_feedback(self, msg):
        if hasattr(self, 'gui'):
            self.gui.on_motor_feedback(
                msg.left_hip,
                msg.left_knee,
                msg.right_hip,
                msg.right_knee,
            )
        
        if not self.running:
            return
        
        if not self.holding:
            self.get_logger().info("Checking pose")
            if self.pose_reached(msg):
                self.holding = True
                self.start_hold_timer()

    # gait handling
    def execute_posture(self, posture_name):
        self.get_logger().info(f"execute_posture({posture_name})")
        self.stop_gait()
        if posture_name not in self.poses:
            self.get_logger().error(f"Unknown posture: {posture_name}")
            return
        pose = self.poses[posture_name]
        left_hip = math.degrees(pose["left_hip_joint"])
        left_knee = math.degrees(pose["left_knee_joint"])
        right_hip = math.degrees(pose["right_hip_joint"])
        right_knee = math.degrees(pose["right_knee_joint"])
        self.publish_joint_state(left_hip, left_knee, right_hip, right_knee)
        self.publish_motor_angles(left_hip, left_knee, right_hip, right_knee)

    def start_gait(self, gait_name, repeats=5, hold_time=2.0):
        self.get_logger().info("start_gait()")
        self.current_gait = self.gaits[gait_name]
        self.current_step = 0
        
        self.current_repeat = 0
        self.total_repeats = repeats

        self.hold_time = hold_time
        self.running = True
        self.holding = False

        self.send_current_pose()
    
    def send_current_pose(self):
        pose_name = self.current_gait[self.current_step]
        pose = self.poses[pose_name]

        self.publish_joint_state(
            math.degrees(pose["left_hip_joint"]),
            math.degrees(pose["left_knee_joint"]),
            math.degrees(pose["right_hip_joint"]),
            math.degrees(pose["right_knee_joint"]),
        )
        self.publish_motor_angles(
            math.degrees(pose["left_hip_joint"]),
            math.degrees(pose["left_knee_joint"]),
            math.degrees(pose["right_hip_joint"]),
            math.degrees(pose["right_knee_joint"]),
        )
    
    def pose_reached(self, msg):
        pose_name = self.current_gait[self.current_step]
        target = self.poses[pose_name]
        tolerance = 2.0
        return (
            abs(msg.left_hip - math.degrees(target["left_hip_joint"])) < tolerance and
            abs(msg.left_knee - math.degrees(target["left_knee_joint"])) < tolerance and
            abs(msg.right_hip - math.degrees(target["right_hip_joint"])) < tolerance and
            abs(msg.right_knee - math.degrees(target["right_knee_joint"])) < tolerance
        )
    
    def start_hold_timer(self):
        self.get_logger().info(f"Starting hold timer: {self.hold_time}s")
        if self.hold_timer is not None:
            self.hold_timer.cancel()
        
        self.hold_timer = self.create_timer(
            self.hold_time, self.next_step
        )

    def next_step(self):
        self.hold_timer.cancel()
        self.current_step += 1
        if self.current_step >= len(self.current_gait):
            self.current_step = 0
            self.current_repeat += 1

            if self.current_repeat >= self.total_repeats:
                self.stop_gait()
                return
        
        self.holding = False
        self.send_current_pose()
            
    def stop_gait(self):
        self.running = False
        self.current_step = 0
        self.current_repeat = 0

        if self.hold_timer is not None:
            self.hold_timer.cancel()
