import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
import math

class ExoJointStateNode(Node):
    def __init__(self):
        super().__init__("exo_joint_state_node")

        self.publisher = self.create_publisher(JointState,'joint_states', 10)
        self.set_initial_position()
        # self.timer = self.create_timer(0.05, self.publish_joint_state)
        self.time = 0
    
    def publish_joint_state(self):
        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()

        msg.name = [
            "left_hip_joint",
            "left_knee_joint",
            "right_hip_joint",
            "right_knee_joint",
        ]
        phase = self.time

        # Hip motion: 0 -> 90 degrees
        left_hip = (math.pi / 4) * (1 + math.sin(phase))
        right_hip = (math.pi / 4) * (1 + math.sin(phase + math.pi))

        # Knee bends only when the leg is lifted
        left_knee = -(math.pi / 4) * max(0.0, math.sin(phase))
        right_knee = -(math.pi / 4) * max(0.0, math.sin(phase + math.pi))

        msg.position = [
            left_hip,
            left_knee,
            right_hip,
            right_knee,
        ]

        self.publisher.publish(msg)
        self.time += 0.08

    def set_initial_position(self):
        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()

        msg.name = [
            "left_hip_joint",
            "left_knee_joint",
            "right_hip_joint",
            "right_knee_joint",
        ]
        
        msg.position = [
            0.0,
            0.0,
            0.0,
            0.0,
        ]

        self.publisher.publish(msg)
        
def main(args=None):
    rclpy.init(args=args)
    node = ExoJointStateNode()
    rclpy.spin(node=node)
    node.destroy_node()
    rclpy.shutdown()
 
if __name__ == "__main__":
    main()