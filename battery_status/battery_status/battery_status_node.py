#!/usr/bin/env python3
"""
battery_status_node.py
----------------------
Publishes battery percentage and voltage to the /battery_status topic.

Current behaviour (ESP32 not connected):
    - Simulates a realistic 12 V Li-Po (3S) discharge curve with small random noise.
      Voltage range: 9.0 V (dead) → 12.6 V (full).

Future behaviour (ESP32 connected):
    - Reads lines from the serial port matching the pattern:
          BAT:<percentage>:<voltage>
      e.g.  BAT:78.5:11.8
      and publishes real values.

Topic published:
    /battery_status  (exoskeleton_interfaces/msg/BatteryStatus)
        float32 percentage   # 0.0 – 100.0 %
        float32 voltage      # Volts  (e.g. 11.8 V for a 12 V 3S Li-Po)
"""

import rclpy
from rclpy.node import Node
from exoskeleton_interfaces.msg import BatteryStatus

import random
import threading
import time


class BatteryStatusNode(Node):
    def __init__(self):
        super().__init__('battery_status_node')

        # ── Parameters ──────────────────────────────────────────────────────
        self.declare_parameter('publish_rate_hz', 1.0)    # how often to publish
        self.declare_parameter('serial_port', '/dev/ttyUSB0')
        self.declare_parameter('baud_rate', 115200)
        self.declare_parameter('use_serial', False)       # set True when ESP32 ready

        rate_hz = self.get_parameter('publish_rate_hz').get_parameter_value().double_value
        port    = self.get_parameter('serial_port').get_parameter_value().string_value
        baud    = self.get_parameter('baud_rate').get_parameter_value().integer_value
        use_ser = self.get_parameter('use_serial').get_parameter_value().bool_value

        # ── Publisher ────────────────────────────────────────────────────────
        self._pub = self.create_publisher(BatteryStatus, '/battery_status', 10)

        # ── Simulated battery state ──────────────────────────────────────────
        # Starts at a random level between 70–95 % and slowly drains
        self._sim_pct  = random.uniform(70.0, 95.0)
        self._drain_hz = rate_hz   # rate used to compute drain per tick

        # ── Serial reader is disabled in this node ───────────────────────────
        # When use_serial is True, serial_bridge_node handles the serial port
        # and publishes the battery status directly.
        self._serial = None
        self._serial_pct = None
        self._serial_volt = None
        self._reader_thread = None

        # ── Publish timer ────────────────────────────────────────────────────
        self._timer = self.create_timer(1.0 / rate_hz, self._publish)

        self.get_logger().info(
            f'[BatteryStatusNode] Started. '
            f'Mode: {"SERIAL" if use_ser else "SIMULATION"}. '
            f'Publishing /battery_status @ {rate_hz} Hz.'
        )

    # ── Serial helpers ───────────────────────────────────────────────────────

    def _open_serial(self, port: str, baud: int) -> None:
        pass

    def _serial_reader_loop(self) -> None:
        pass

    # ── Simulation helper ────────────────────────────────────────────────────

    def _simulate(self):
        """
        Simulate a 12 V Li-Po discharge (3S pack):
        - Voltage range: 9.0 V (dead) – 12.6 V (full)
        - Drain ~0.01 % per second + small noise
        """
        drain = 0.01 / self._drain_hz      # % per tick
        self._sim_pct -= drain
        self._sim_pct += random.gauss(0, 0.05)   # tiny noise
        self._sim_pct  = max(0.0, min(100.0, self._sim_pct))

        # Map pct → voltage (3S Li-Po 12 V: 9.0 V – 12.6 V)
        voltage = 9.0 + (self._sim_pct / 100.0) * 3.6
        voltage += random.gauss(0, 0.02)   # sensor noise

        return round(self._sim_pct, 1), round(voltage, 2)

    # ── Publish callback ─────────────────────────────────────────────────────

    def _publish(self) -> None:
        use_ser = self.get_parameter('use_serial').get_parameter_value().bool_value
        if use_ser:
            # If using serial, serial_bridge_node handles publishing real data.
            return

        msg = BatteryStatus()
        # Simulation
        pct, volt      = self._simulate()
        msg.percentage = pct
        msg.voltage    = volt
        msg.connected  = False

        self._pub.publish(msg)
        self.get_logger().debug(
            f'[BatteryStatusNode] Published Sim: {msg.percentage:.1f}%  '
            f'{msg.voltage:.2f} V'
        )


def main(args=None):
    rclpy.init(args=args)
    node = BatteryStatusNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
