import sys

sys.path.insert(
    0,
    "/home/alister/robot1/src/rviz_widget/build/rviz_widget/build/lib.linux-x86_64-cpython-312"
)

from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout
from rviz_widget import RvizWidget

import rclpy

app = QApplication([])
rclpy.init()

window = QWidget()
layout = QVBoxLayout(window)

rviz = RvizWidget()
layout.addWidget(rviz)

window.resize(1000, 700)
window.show()

app.exec()