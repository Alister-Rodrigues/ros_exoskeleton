import math
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from exoskeleton_interfaces.msg import MotorAngles


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
            }

        }

        self.gaits = {
            "knee_bend": [
                "stand_neutral",
                "knee_bend",
                "stand_neutral",
            ],

            "sit_like_bend": [
                "stand_neutral",
                "sitting",
                "stand_neutral",
            ],

            "forward_lean": [
                "stand_neutral",
                "forward_lean",
                "stand_neutral",
            ],

            "backward_lean": [
                "stand_neutral",
                "backward_lean",
                "stand_neutral",
            ],

            "step_prepare": [
                "stand_neutral",
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
        self.get_logger().info("Checking pose")
        if self.pose_reached(msg):
            self.start_hold_timer()

    # gait handling
    def start_gait(self, gait_name, repeats, hold_time):
        self.get_logger().info("start_gait()")
        self.current_gait = self.gaits[gait_name]
        self.current_step = 0
        
        self.current_repeat = 0
        self.total_repeats = repeats

        self.hold_time = hold_time
        self.running = True

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
        
        self.send_current_pose()
            
    def stop_gait(self):
        self.running = False
        self.current_step = 0
        self.current_repeat = 0

        if self.hold_timer is not None:
            self.hold_timer.cancel()
