#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from example_interfaces.msg import String

class RoTalker(Node):
    def __init__(self):
        super().__init__("ali_robot_talker")
        self.talker = self.create_publisher(String, "speaker", 10)

        # self.declare_parameter('timer_secs', 1.0)
        # self.timer_secs = self.get_parameter('timer_secs').value
        self.counter = 0
        self.timer = self.create_timer(self.timer_secs, self.SpeakerHandler)
    
    def SpeakerHandler(self):
        message_value = String()
        message_value.data = f"Online. Counter: {self.counter}"
        self.talker.publish(message_value)
        self.counter += 1

def main(args=None):
    rclpy.init()
    node = RoTalker()
    rclpy.spin(node)
    rclpy.shutdown()

if __name__ == "__main__":
    main()