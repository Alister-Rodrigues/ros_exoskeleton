#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from example_interfaces.msg import String

class RoSpeaker(Node):
    def __init__(self):
        super().__init__("ali_robot_listener")
        self.speaker = self.create_subscription(String, "speaker", self.SpeakerHandler, 10)

    
    def SpeakerHandler(self, msg):
        self.get_logger().info(f"Heard: {msg.data}")

def main(args=None):
    rclpy.init()
    node = RoSpeaker()
    rclpy.spin(node)
    rclpy.shutdown()

if __name__ == "__main__":
    main()