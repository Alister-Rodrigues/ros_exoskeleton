#!/usr/bin/env python3
"""
serial_bridge_node.py
---------------------
Subscribes to /motor_commands (exoskeleton_interfaces/msg/MotorAngles) and
/motor_reset (std_msgs/msg/String) then forwards commands to the ESP32
over a serial port.

Topic:  /motor_commands  -> sends  "1:<left_hip>"  and  "2:<left_knee>"
Topic:  /motor_reset     -> sends  "reset_motors"  when msg.data == "reset_motors"

Also runs a background READER THREAD that prints all incoming serial data
from the ESP32 directly to the terminal.

NO changes are made to the ESP32 firmware.
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Int32
from exoskeleton_interfaces.msg import MotorAngles, BatteryStatus
from std_msgs.msg import String, Int32, Bool

import serial
import threading
import time


class SerialBridgeNode(Node):
    def __init__(self):
        super().__init__('serial_bridge_node')

        # ── Parameters (override at launch or from command line) ────────────
        self.declare_parameter('serial_port', '/dev/ttyUSB0')
        self.declare_parameter('baud_rate', 115200)
        self.declare_parameter('send_interval_ms', 50)  # min ms between sends

        port  = self.get_parameter('serial_port').get_parameter_value().string_value
        baud  = self.get_parameter('baud_rate').get_parameter_value().integer_value
        self._min_interval = (
            self.get_parameter('send_interval_ms').get_parameter_value().integer_value
            / 1000.0
        )

        # ── Open serial port ────────────────────────────────────────────────
        self._serial: serial.Serial | None = None
        self._connect_serial(port, baud)

        # ── Background serial READER thread ─────────────────────────────────
        self._reader_running = False
        if self._serial:
            self._reader_running = True
            self._reader_thread = threading.Thread(
                target=self._serial_reader_loop,
                daemon=True,
                name='serial_reader'
            )
            self._reader_thread.start()

        # ── Rate-limit tracking ─────────────────────────────────────────────
        self._last_send_time = 0.0

        # ── Subscriptions ───────────────────────────────────────────────────
        self.create_subscription(
            MotorAngles,
            '/motor_commands',
            self._motor_commands_callback,
            10
        )

        self.conn_pub = self.create_publisher(Bool, '/esp32_connected', 10)
        self.battery_pub = self.create_publisher(BatteryStatus, '/battery_status', 10)
        self._last_conn_status = None

        self.create_subscription(
            String,
            '/motor_reset',
            self._motor_reset_callback,
            10
        )

        self.create_subscription(
            Int32,
            '/motor_speed',
            self._motor_speed_callback,
            10
        )

        self.get_logger().info(
            f'[SerialBridgeNode] Ready. '
            f'Port: {port} @ {baud} baud. '
            f'Listening on /motor_commands and /motor_reset.'
        )

    # ── Serial helpers ──────────────────────────────────────────────────────

    def _connect_serial(self, port: str, baud: int) -> None:
        """Try to open the serial port; log and continue if not available."""
        try:
            self._serial = serial.Serial(port, baud, timeout=1)
            time.sleep(2)  # Allow ESP32 to reset after serial open
            self.get_logger().info(f'[SerialBridgeNode] Serial port {port} opened.')
        except serial.SerialException as e:
            self._serial = None
            self.get_logger().error(
                f'[SerialBridgeNode] Could not open serial port {port}: {e}'
            )

    def _serial_reader_loop(self) -> None:
        """
        Background thread: continuously read lines from ESP32 and print them.
        Format:
            [ESP32] M1 Tgt: 36.0° Act: 35.8° [OK] | M2 Tgt: -44.0° Act: -43.9° [OK]
        """
        print('\n' + '═' * 60)
        print('  📟  ESP32 SERIAL MONITOR  (live output below)')
        print('═' * 60 + '\n', flush=True)

        def publish_conn(status: bool):
            msg = Bool()
            msg.data = status
            self.conn_pub.publish(msg)

        while self._reader_running:
            if self._serial is None or not self._serial.is_open:
                publish_conn(False)
                
                # Attempt reconnection
                port = self.get_parameter('serial_port').get_parameter_value().string_value
                baud = self.get_parameter('baud_rate').get_parameter_value().integer_value
                try:
                    self._serial = serial.Serial(port, baud, timeout=1)
                    time.sleep(2)  # Allow ESP32 to reset
                    self.get_logger().info(f'[SerialBridgeNode] Successfully reconnected to {port}.')
                except serial.SerialException:
                    pass
                
                time.sleep(0.5)
                continue
            try:
                raw = self._serial.readline()
                if raw:
                    publish_conn(True)
                    line = raw.decode('utf-8', errors='replace').strip()
                    if line:
                        print(f'[ESP32] {line}', flush=True)
                        if "Battery Voltage" in line and "Battery :" in line:
                            try:
                                # Format: "Battery Voltage : 12.55 V    Battery : 98 %"
                                parts = line.split("Battery :")
                                v_str = parts[0].split(":")[1].replace("V", "").strip()
                                p_str = parts[1].replace("%", "").strip()
                                
                                bat_msg = BatteryStatus()
                                bat_msg.voltage = float(v_str)
                                bat_msg.percentage = float(p_str)
                                bat_msg.connected = True
                                self.battery_pub.publish(bat_msg)
                            except Exception as e:
                                self.get_logger().error(f"[SerialBridgeNode] Error parsing battery status: {e}")
            except serial.SerialException as e:
                publish_conn(False)
                self.get_logger().error(f'[SerialBridgeNode] Serial read error: {e}')
                if self._serial:
                    self._serial.close()
                self._serial = None
                time.sleep(0.5)
            except Exception:
                publish_conn(False)
                time.sleep(0.1)

    def _send_command(self, cmd: str) -> None:
        """Send a newline-terminated command string to the ESP32."""
        if self._serial is None or not self._serial.is_open:
            self.get_logger().warn(
                f'[SerialBridgeNode] Serial not open, dropping command: {cmd}'
            )
            return

        try:
            full_cmd = cmd.strip() + '\n'
            self._serial.write(full_cmd.encode('utf-8'))
            self._last_send_time = time.time()
            print(f'[>> SENT] {cmd}', flush=True)
            self.get_logger().info(f'[SerialBridgeNode] >> SENT: {cmd}')
        except serial.SerialException as e:
            self.get_logger().error(f'[SerialBridgeNode] Serial write error: {e}')

    # ── Callbacks ───────────────────────────────────────────────────────────

    def _motor_commands_callback(self, msg: MotorAngles) -> None:
        """
        Receive MotorAngles and forward to ESP32:
          left_hip  -> Motor 1  ->  "1:<angle>"
          left_knee -> Motor 2  ->  "2:<angle>"
        Angles are rounded to 1 decimal place.
        """
        hip_cmd  = f'1:{msg.left_hip:.1f}'
        knee_cmd = f'2:{msg.left_knee:.1f}'

        self.get_logger().info(
            f'[SerialBridgeNode] Received -> '
            f'left_hip={msg.left_hip:.1f}°  left_knee={msg.left_knee:.1f}°'
        )

        self._send_command(hip_cmd)
        self._send_command(knee_cmd)

    def _motor_reset_callback(self, msg: String) -> None:
        """
        Receive reset command from /motor_reset topic.
        When data == 'reset_motors', send 'reset_motors' to ESP32.
        """
        if msg.data.strip() == 'reset_motors':
            self.get_logger().info(
                '[SerialBridgeNode] RESET command received — homing both motors.'
            )
            print('\n[!! RESET] Sending homing command to ESP32...\n', flush=True)
            self._send_command('reset_motors')
        else:
            self.get_logger().warn(
                f'[SerialBridgeNode] Unknown reset command: "{msg.data}"'
            )

    def _motor_speed_callback(self, msg: Int32) -> None:
        """
        Receive speed command from /motor_speed topic.
        Sends 'speed:<val>' to ESP32.
        """
        speed = max(0, min(100, msg.data))
        self.get_logger().info(f'[SerialBridgeNode] Setting max speed to {speed}%')
        self._send_command(f'speed:{speed}')

    # ── Cleanup ─────────────────────────────────────────────────────────────

    def destroy_node(self):
        self._reader_running = False
        if self._serial and self._serial.is_open:
            self._serial.close()
            self.get_logger().info('[SerialBridgeNode] Serial port closed.')
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = SerialBridgeNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
