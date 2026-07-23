import rclpy
from rclpy.node import Node
from exoskeleton_interfaces.msg import MotorAngles

class MotorNode(Node):
    def __init__(self):
        super().__init__("motor_node")

        self.publisher = self.create_publisher(
            MotorAngles, 'motor_commands', 10
        )
        self.subscriber = self.create_subscription(
            MotorAngles, 'motor_feedback', self.feedback_callback, 10
        )
    
    def publish_motor_angles(self, left_hip, left_knee, right_hip, right_knee):
        self.get_logger().info('test-pub')
        msg = MotorAngles()
        msg.left_hip = left_hip
        msg.left_knee = left_knee
        msg.right_hip = right_hip
        msg.right_knee = right_knee

        self.publisher.publish(msg)
    
    def feedback_callback(self, msg):
        self.get_logger().info('test-sub')
        if hasattr(self, "gui"):
            self.gui.on_motor_feedback(
                msg.left_hip,
                msg.left_knee,
                msg.right_hip,
                msg.right_knee,
            )
        
def main(args=None):
    rclpy.init(args=args)
    node = MotorNode()
    rclpy.spin(node=node)
    node.destroy_node()
    rclpy.shutdown()
 
if __name__ == "__main__":
    main()