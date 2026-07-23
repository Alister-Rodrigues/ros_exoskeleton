import math
import rclpy
import sys
import random
from datetime import datetime
import math
# pyqt imports
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QRectF, QPointF
from PyQt6.QtGui import QFont, QColor, QPainter, QPen, QPainterPath, QBrush, QConicalGradient
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QGridLayout,
    QFrame, QPushButton, QSizePolicy, QGraphicsDropShadowEffect, QStackedWidget,
    QSlider, QButtonGroup
)
# Node imports
import rclpy
from dashboard.joint_state_node import JointStateNode

# ----------------------------------------------------------------------
# Palette (dark theme, shared across every page)
# ----------------------------------------------------------------------
BG = "#0a0e21"
SIDEBAR_BG = "#0c1128"
TOPBAR_BG = "#0c1128"
CARD_BG = "#121a37"
CARD_BG_2 = "#0e1530"
BORDER = "#232c50"
TEXT = "#eef1fb"
TEXT_MUTED = "#7c88ac"
TEXT_DIM = "#525d80"

GREEN = "#22c55e"
GREEN_BG = "#12251c"
BLUE = "#3b82f6"
BLUE_BG = "#0f1c33"
PURPLE = "#a855f7"
PURPLE_BG = "#1d1533"
ORANGE = "#f59e0b"
ORANGE_BG = "#2a2013"
RED = "#ef4444"
RED_BG = "#2a1417"
CYAN = "#22d3ee"


def shadow(blur=22, y=4, alpha=90):
    eff = QGraphicsDropShadowEffect()
    eff.setBlurRadius(blur)
    eff.setOffset(0, y)
    eff.setColor(QColor(0, 0, 0, alpha))
    return eff


def card_frame(radius=14, bg=CARD_BG, border=BORDER):
    f = QFrame()
    f.setStyleSheet(f"QFrame {{ background:{bg}; border:1px solid {border}; border-radius:{radius}px; }}")
    f.setGraphicsEffect(shadow())
    return f


def section_title(text, color=TEXT):
    lab = QLabel(text)
    lab.setStyleSheet(f"color:{color}; font-size:13px; font-weight:700; letter-spacing:0.5px; border:none; background:transparent;")
    return lab


def pill(text, fg, bg):
    lab = QLabel(text)
    lab.setStyleSheet(
        f"QLabel {{ color:{fg}; background:{bg}; padding:3px 10px;"
        f"border-radius:9px; font-weight:700; font-size:11px; }}"
    )
    return lab


# ----------------------------------------------------------------------
# Reusable painted widgets
# ----------------------------------------------------------------------
class Sparkline(QWidget):
    def __init__(self, color, parent=None, points=20):
        super().__init__(parent)
        self.color = QColor(color)
        self.values = [random.uniform(0.2, 0.8) for _ in range(points)]
        self.setMinimumHeight(34)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def tick(self):
        self.values.pop(0)
        nxt = max(0.08, min(0.92, self.values[-1] + random.uniform(-0.2, 0.2)))
        self.values.append(nxt)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        n = len(self.values)
        step = w / (n - 1) if n > 1 else w
        pts = [(i * step, h - (v * (h - 4)) - 2) for i, v in enumerate(self.values)]
        path = QPainterPath()
        path.moveTo(*pts[0])
        for x, y in pts[1:]:
            path.lineTo(x, y)
        pen = QPen(self.color, 1.8)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawPath(path)


class SemiGauge(QWidget):
    """Half-circle gauge, e.g. Assistance Level 65%."""

    def __init__(self, value, color, subtitle="", parent=None):
        super().__init__(parent)
        self.value = value
        self.color = QColor(color)
        self.subtitle = subtitle
        self.setMinimumSize(180, 120)

    def set_value(self, v):
        self.value = v
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        side = min(w, h * 2)
        cx, cy = w / 2, h * 0.82
        radius = side / 2 - 12
        rect = QRectF(cx - radius, cy - radius, radius * 2, radius * 2)

        track = QPen(QColor(BORDER), 12, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(track)
        p.drawArc(rect, 0 * 16, 180 * 16)

        arc_pen = QPen(self.color, 12, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(arc_pen)
        span = int(180 * (self.value / 100) * 16)
        p.drawArc(rect, 180 * 16, -span)

        p.setPen(QPen(QColor(TEXT)))
        f = QFont("Segoe UI", 18, QFont.Weight.Bold)
        p.setFont(f)
        p.drawText(QRectF(0, cy - radius - 6, w, 30), Qt.AlignmentFlag.AlignCenter, f"{self.value}%")

        if self.subtitle:
            p.setPen(QPen(QColor(TEXT_MUTED)))
            p.setFont(QFont("Segoe UI", 9))
            p.drawText(QRectF(0, cy - radius + 20, w, 20), Qt.AlignmentFlag.AlignCenter, self.subtitle)


class Bar(QWidget):
    """Thin horizontal progress bar used for joint targets / impedance level."""

    def __init__(self, value, color, parent=None):
        super().__init__(parent)
        self.value = value
        self.color = QColor(color)
        self.setFixedHeight(8)
        self.setMinimumWidth(80)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(BORDER))
        p.drawRoundedRect(0, 0, w, h, h / 2, h / 2)
        fw = max(h, w * (self.value / 100))
        p.setBrush(self.color)
        p.drawRoundedRect(0, 0, int(fw), h, h / 2, h / 2)


class LegGraphic(QWidget):
    """Stylised articulated exoskeleton."""

    def __init__(self, hip_l=None, knee_l=None, hip_r=None, knee_r=None, parent=None):
        super().__init__(parent)

        self.hip_l = hip_l
        self.knee_l = knee_l
        self.hip_r = hip_r
        self.knee_r = knee_r

        self.hip_angle_l = 0
        self.knee_angle_l = 0

        self.hip_angle_r = 0
        self.knee_angle_r = 0

        self.setMinimumSize(220, 320)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        cx = w / 2
        top = h * 0.06

        thigh_length = h * 0.36
        shin_length = h * 0.33
        foot_length = 28

        # Hip belt
        p.setPen(QPen(QColor("#3a4568"), 6, cap=Qt.PenCapStyle.RoundCap))
        p.drawLine(
            QPointF(cx - w * 0.22, top),
            QPointF(cx + w * 0.22, top),
        )

        p.setBrush(QColor("#1c243f"))
        p.setPen(QPen(QColor("#3a4568"), 2))
        p.drawRoundedRect(
            QRectF(cx - w * 0.14, top - 10, w * 0.28, 22),
            10,
            10,
        )

        legs = [
            (-w * 0.13, self.hip_angle_l, self.knee_angle_l,
            self.hip_l, self.knee_l),

            ( w * 0.13, self.hip_angle_r, self.knee_angle_r,
            self.hip_r, self.knee_r),
        ]

        for offset, hip_angle, knee_angle, hip_color, knee_color in legs:

            hip = QPointF(cx + offset, top + 14)

            hip_rad = math.radians(hip_angle)

            knee = QPointF(
                hip.x() + thigh_length * math.sin(hip_rad),
                hip.y() + thigh_length * math.cos(hip_rad)
            )

            shin_rad = hip_rad + math.radians(knee_angle)

            ankle = QPointF(
                knee.x() + shin_length * math.sin(shin_rad),
                knee.y() + shin_length * math.cos(shin_rad)
            )

            foot_end = QPointF(
                ankle.x() + foot_length * math.cos(shin_rad),
                ankle.y() - foot_length * math.sin(shin_rad)
            )

            thigh_pen = QPen(
                QColor(hip_color) if hip_color else QColor("#374162"),
                10,
                cap=Qt.PenCapStyle.RoundCap
            )

            shin_pen = QPen(
                QColor(knee_color) if knee_color else QColor("#374162"),
                10,
                cap=Qt.PenCapStyle.RoundCap
            )

            p.setPen(thigh_pen)
            p.drawLine(hip, knee)

            p.setPen(shin_pen)
            p.drawLine(knee, ankle)

            p.setPen(QPen(QColor("#3a4568"), 6, cap=Qt.PenCapStyle.RoundCap))
            p.drawLine(ankle, foot_end)

            hip_outline = QColor(hip_color) if hip_color else QColor("#4a5578")
            knee_outline = QColor(knee_color) if knee_color else QColor("#4a5578")

            p.setBrush(QColor("#1c243f"))

            p.setPen(QPen(hip_outline, 3))
            p.drawEllipse(hip, 10, 10)

            p.setPen(QPen(knee_outline, 3))
            p.drawEllipse(knee, 13, 13)

            p.setPen(QPen(QColor("#4a5578"), 3))
            p.drawEllipse(ankle, 8, 8)

# ----------------------------------------------------------------------
# Title bar + status strip + bottom bar
# ----------------------------------------------------------------------
class TitleBar(QFrame):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.setFixedHeight(46)
        self.setStyleSheet(f"background:{TOPBAR_BG}; border-bottom:1px solid {BORDER};")
        self._drag_pos = None

        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 0, 10, 0)
        lay.setSpacing(10)

        icon = QLabel("🦿")
        icon.setStyleSheet("font-size:16px; background:transparent;")
        lay.addWidget(icon)

        title = QLabel("EMG Exoskeleton Control System")
        title.setStyleSheet(f"color:{TEXT}; font-size:14px; font-weight:600; background:transparent;")
        lay.addWidget(title)
        lay.addStretch()

        self.conn_label = QLabel("📶 Connected")
        self.conn_label.setStyleSheet(f"color:{GREEN}; font-size:12px; font-weight:600; background:transparent;")
        lay.addWidget(self.conn_label)

        batt = QLabel("🔋 78%")
        batt.setStyleSheet(f"color:{GREEN}; font-size:12px; font-weight:600; background:transparent;")
        lay.addWidget(batt)
        lay.addSpacing(6)

        for symbol, slot in (
            ("—", self.window.showMinimized),
            ("□", self._toggle_max),
            ("✕", self.window.close),
        ):
            btn = QPushButton(symbol)
            btn.setFixedSize(36, 30)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            hover = RED if symbol == "✕" else "#1c2648"
            btn.setStyleSheet(
                f"QPushButton {{ color:{TEXT}; background:transparent; border:none; font-size:12px; border-radius:6px; }}"
                f"QPushButton:hover {{ background:{hover}; }}"
            )
            btn.clicked.connect(slot)
            lay.addWidget(btn)

    def _toggle_max(self):
        if self.window.isMaximized():
            self.window.showNormal()
        else:
            self.window.showMaximized()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self.window.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag_pos and e.buttons() & Qt.MouseButton.LeftButton:
            self.window.move(e.globalPosition().toPoint() - self._drag_pos)


class StatCard(QFrame):
    def __init__(self, icon_char, icon_color, label, value, value_color=TEXT, sub=None):
        super().__init__()
        self.setStyleSheet(f"QFrame {{ background:{CARD_BG}; border:1px solid {BORDER}; border-radius:12px; }}")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 12, 18, 12)
        lay.setSpacing(12)

        icon = QLabel(icon_char)
        icon.setStyleSheet(f"color:{icon_color}; font-size:19px; border:none; background:transparent;")
        lay.addWidget(icon)

        col = QVBoxLayout()
        col.setSpacing(1)
        lab = QLabel(label)
        lab.setStyleSheet(f"color:{TEXT_MUTED}; font-size:11.5px; border:none; background:transparent;")
        col.addWidget(lab)

        self.value_label = QLabel(value)
        self.value_label.setStyleSheet(f"color:{value_color}; font-size:16px; font-weight:700; border:none; background:transparent;")
        col.addWidget(self.value_label)

        if sub:
            sub_l = QLabel(sub)
            sub_l.setStyleSheet(f"color:{TEXT_MUTED}; font-size:10.5px; border:none; background:transparent;")
            col.addWidget(sub_l)

        lay.addLayout(col)
        lay.addStretch()


class ModeStatCard(QFrame):
    """Big-number 'Current Mode' card."""

    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"QFrame {{ background:{CARD_BG}; border:1px solid {BORDER}; border-radius:12px; }}")
        self.lay = QHBoxLayout(self)
        self.lay.setContentsMargins(16, 10, 18, 10)
        self.lay.setSpacing(12)

        self.number = QLabel("-")
        self.number.setFixedWidth(28)
        self.number.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lay.addWidget(self.number)

        col = QVBoxLayout()
        col.setSpacing(1)
        lab = QLabel("Current Mode")
        lab.setStyleSheet(f"color:{TEXT_MUTED}; font-size:11.5px; border:none; background:transparent;")
        col.addWidget(lab)
        self.name = QLabel("Not Selected")
        self.name.setStyleSheet(f"color:{TEXT}; font-size:14.5px; font-weight:700; border:none; background:transparent;")
        col.addWidget(self.name)
        self.sub = QLabel("")
        self.sub.setStyleSheet(f"color:{TEXT_MUTED}; font-size:10.5px; border:none; background:transparent;")
        col.addWidget(self.sub)
        self.lay.addLayout(col)
        self.lay.addStretch()

    def set_mode(self, number, name, sub, color):
        self.number.setText(str(number) if number else "-")
        self.number.setStyleSheet(f"color:{color}; font-size:22px; font-weight:800; border:none; background:transparent;")
        self.name.setText(name)
        self.name.setStyleSheet(f"color:{color}; font-size:14.5px; font-weight:700; border:none; background:transparent;")
        self.sub.setText(sub)


class StatusStrip(QFrame):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("background:transparent; border:none;")
        self.lay = QHBoxLayout(self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.lay.setSpacing(14)

        self.system_card = StatCard("✔", GREEN, "System Status", "GOOD", GREEN)
        self.battery_card = StatCard("🔋", GREEN, "Battery", "78%", GREEN, "24.6 V · Li-Po")
        self.emg_card = StatCard("〜", GREEN, "EMG Signal Quality", "GOOD", GREEN)
        self.mode_card = ModeStatCard()
        self.time_card = StatCard("🕒", TEXT_MUTED, "Time", "12:45:30 PM", TEXT, "12 Jul 2025")

        for w in (self.system_card, self.battery_card, self.emg_card, self.mode_card, self.time_card):
            self.lay.addWidget(w, 1)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(1000)
        self._tick()

    def set_third_card(self, mode="emg"):
        """Home page shows Connection instead of EMG Signal Quality."""
        if mode == "conn":
            self.emg_card.value_label.setText("Connected")
        else:
            self.emg_card.value_label.setText("GOOD")

    def set_time_mode(self, mode="time"):
        if mode == "session":
            self.time_card.value_label.parent()  # no-op, label already generic

    def _tick(self):
        now = datetime.now()
        self.time_card.value_label.setText(now.strftime("%I:%M:%S %p"))


class BottomBar(QFrame):
    def __init__(self):
        super().__init__()
        self.setFixedHeight(36)
        self.setStyleSheet(f"background:{TOPBAR_BG}; border-top:1px solid {BORDER};")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(20, 0, 20, 0)

        self.left = QLabel("System ready.")
        self.left.setStyleSheet(f"color:{TEXT_MUTED}; font-size:12px; background:transparent;")
        lay.addWidget(self.left)
        lay.addStretch()

        mid = QLabel("ROS 2  |  All Systems Operational")
        mid.setStyleSheet(f"color:{TEXT_MUTED}; font-size:12px; background:transparent;")
        lay.addWidget(mid)
        lay.addStretch()

        right = QLabel("🔊 Audio Feedback: ON")
        right.setStyleSheet(f"color:{TEXT_MUTED}; font-size:12px; background:transparent;")
        lay.addWidget(right)

    def set_message(self, text, color=TEXT_MUTED):
        self.left.setText(text)
        self.left.setStyleSheet(f"color:{color}; font-size:12px; background:transparent;")


# ----------------------------------------------------------------------
# Sidebar
# ----------------------------------------------------------------------
class NavButton(QPushButton):
    def __init__(self, icon_char, title, subtitle, accent):
        super().__init__()
        self.accent = accent
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(58 if subtitle else 44)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 6, 12, 6)
        lay.setSpacing(12)

        icon = QLabel(icon_char)
        icon.setStyleSheet("font-size:16px; background:transparent; border:none;")
        lay.addWidget(icon)

        col = QVBoxLayout()
        col.setSpacing(0)
        self.title_l = QLabel(title)
        self.title_l.setStyleSheet("font-size:13px; font-weight:700; background:transparent; border:none;")
        col.addWidget(self.title_l)
        if subtitle:
            self.sub_l = QLabel(subtitle)
            self.sub_l.setStyleSheet(f"font-size:10.5px; color:{TEXT_MUTED}; background:transparent; border:none;")
            col.addWidget(self.sub_l)
        else:
            self.sub_l = None
        lay.addLayout(col)
        lay.addStretch()

        self._apply_style(False)
        self.toggled.connect(self._apply_style)

    def _apply_style(self, checked):
        if checked:
            self.setStyleSheet(
                f"""
                QPushButton {{
                    background:{self.accent}22;
                    border:none;
                    border-left:3px solid {self.accent};
                    text-align:left;
                }}
                """
            )
            self.title_l.setStyleSheet(f"font-size:13px; font-weight:700; color:{self.accent}; background:transparent; border:none;")
        else:
            self.setStyleSheet(
                """
                QPushButton { background:transparent; border:none; border-left:3px solid transparent; text-align:left; }
                QPushButton:hover { background:#141c3c; }
                """
            )
            self.title_l.setStyleSheet(f"font-size:13px; font-weight:700; color:{TEXT}; background:transparent; border:none;")


class Sidebar(QFrame):
    navigate = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.setFixedWidth(208)
        self.setStyleSheet(f"background:{SIDEBAR_BG}; border-right:1px solid {BORDER};")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 14, 0, 14)
        lay.setSpacing(2)

        self.group = QButtonGroup(self)
        self.group.setExclusive(True)

        specs = [
            ("🏠", "HOME", "", TEXT),
            ("〜", "MODE 1", "EMG-Driven Control", GREEN),
            ("🚶", "MODE 2", "Pre-Programmed Gait", BLUE),
            ("🎛", "MODE 3", "Impedance Control", PURPLE),
            ("⚙", "PARAMETERS", "", TEXT),
            ("📟", "DIAGNOSTICS", "", TEXT),
        ]
        self.buttons = []
        for i, (icon, title, sub, accent) in enumerate(specs):
            btn = NavButton(icon, title, sub, accent)
            self.group.addButton(btn, i)
            lay.addWidget(btn)
            self.buttons.append(btn)
            if i == 3:
                sep = QFrame()
                sep.setFixedHeight(1)
                sep.setStyleSheet(f"background:{BORDER}; margin:10px 16px;")
                lay.addWidget(sep)

        self.buttons[0].setChecked(True)
        self.group.idClicked.connect(self.navigate.emit)

        lay.addStretch()

        voice = QFrame()
        voice.setStyleSheet(f"background:{CARD_BG_2}; border:1px solid {BORDER}; border-radius:10px; margin:0 14px;")
        v_lay = QHBoxLayout(voice)
        v_lay.setContentsMargins(12, 10, 12, 10)
        icon = QLabel("🔊")
        icon.setStyleSheet("font-size:14px; background:transparent; border:none;")
        v_lay.addWidget(icon)
        col = QVBoxLayout()
        col.setSpacing(0)
        t = QLabel("VOICE FEEDBACK")
        t.setStyleSheet(f"color:{TEXT}; font-size:10.5px; font-weight:700; background:transparent; border:none;")
        s = QLabel("ⓘ ON")
        s.setStyleSheet(f"color:{GREEN}; font-size:10.5px; font-weight:600; background:transparent; border:none;")
        col.addWidget(t)
        col.addWidget(s)
        v_lay.addLayout(col)
        v_lay.addStretch()
        lay.addWidget(voice)

    def select(self, index):
        self.buttons[index].setChecked(True)


# ----------------------------------------------------------------------
# Pages
# ----------------------------------------------------------------------
class ChannelRow(QFrame):
    def __init__(self, name, value, color):
        super().__init__()
        self.setStyleSheet("background:transparent; border:none;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 8, 0, 8)
        lay.setSpacing(4)
        top = QHBoxLayout()
        n = QLabel(name)
        n.setStyleSheet(f"color:{TEXT_MUTED}; font-size:12px; border:none; background:transparent;")
        top.addWidget(n)
        top.addStretch()
        self.val = QLabel(value)
        self.val.setStyleSheet(f"color:{color}; font-size:13px; font-weight:700; border:none; background:transparent;")
        top.addWidget(self.val)
        lay.addLayout(top)
        self.spark = Sparkline(color)
        lay.addWidget(self.spark)


class HomePage(QWidget):
    request_nav = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(16)

        heading = QLabel("EMG-Controlled Humanoid Lower-Limb Exoskeleton")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        heading.setStyleSheet(f"color:{TEXT}; font-size:22px; font-weight:800; border:none;")
        lay.addWidget(heading)

        panel = card_frame()
        p_lay = QVBoxLayout(panel)
        p_lay.setContentsMargins(22, 20, 22, 20)
        p_lay.setSpacing(14)
        p_lay.addWidget(section_title("⚙  OPERATING MODES"))

        cards_row = QHBoxLayout()
        cards_row.setSpacing(14)
        cards_row.addWidget(self._mode_card(1, "MODE 1", "EMG-Driven Control", "Voluntary Control",
                                             "Detects muscle intent from EMG signals and provides proportional assistance.",
                                             GREEN, GREEN_BG))
        cards_row.addWidget(self._mode_card(2, "MODE 2", "Pre-Programmed Gait", "Automatic Gait Patterns",
                                             "Executes predefined gait trajectories for walking, stairs and sit-to-stand.",
                                             BLUE, BLUE_BG))
        cards_row.addWidget(self._mode_card(3, "MODE 3", "Impedance Control", "Assist / Resist",
                                             "Implements mass-spring-damper behavior for assistance or resistance.",
                                             PURPLE, PURPLE_BG))
        p_lay.addLayout(cards_row)
        lay.addWidget(panel)

        emg_panel = card_frame()
        e_lay = QVBoxLayout(emg_panel)
        e_lay.setContentsMargins(22, 18, 22, 18)
        e_lay.setSpacing(12)
        e_lay.addWidget(section_title("📈  EMG SIGNAL OVERVIEW (mV)"))
        grid = QGridLayout()
        grid.setSpacing(14)
        specs = [("Channel 1", "0.32 mV", GREEN), ("Channel 2", "0.28 mV", BLUE),
                 ("Channel 3", "0.31 mV", ORANGE), ("Channel 4", "0.29 mV", PURPLE)]
        self.channels = []
        for i, (n, v, c) in enumerate(specs):
            card = card_frame(radius=10)
            cl = QVBoxLayout(card)
            cl.setContentsMargins(14, 10, 14, 10)
            row = ChannelRow(n, v, c)
            cl.addWidget(row)
            self.channels.append(row)
            grid.addWidget(card, 0, i)
        e_lay.addLayout(grid)
        lay.addWidget(emg_panel)
        lay.addStretch()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(700)

    def _tick(self):
        for row in self.channels:
            row.spark.tick()
            row.val.setText(f"{row.spark.values[-1]:.2f} mV")

    def _mode_card(self, index, badge, title, subtitle, desc, accent, tint):
        frame = QFrame()
        frame.setCursor(Qt.CursorShape.PointingHandCursor)
        frame.setStyleSheet(f"QFrame {{ background:{tint}; border:1.5px solid {accent}55; border-radius:12px; }}")
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(18, 16, 18, 18)
        lay.setSpacing(8)

        b = QLabel(badge)
        b.setFixedWidth(70)
        b.setAlignment(Qt.AlignmentFlag.AlignCenter)
        b.setStyleSheet(f"background:{accent}; color:#0a0e21; font-weight:800; font-size:11px; padding:4px 0; border-radius:10px;")
        row = QHBoxLayout()
        row.addWidget(b)
        row.addStretch()
        lay.addLayout(row)

        t = QLabel(title)
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        t.setStyleSheet(f"color:{accent}; font-size:15px; font-weight:700; border:none; background:transparent;")
        lay.addWidget(t)

        s = QLabel(subtitle)
        s.setAlignment(Qt.AlignmentFlag.AlignCenter)
        s.setStyleSheet(f"color:{TEXT}; font-size:12.5px; font-weight:700; border:none; background:transparent;")
        lay.addWidget(s)

        d = QLabel(desc)
        d.setAlignment(Qt.AlignmentFlag.AlignCenter)
        d.setWordWrap(True)
        d.setStyleSheet(f"color:{TEXT_MUTED}; font-size:11.5px; border:none; background:transparent;")
        lay.addWidget(d)

        def clicked(event, idx=index):
            self.request_nav.emit(idx)
        frame.mousePressEvent = clicked
        return frame


class InfoBar(QFrame):
    def __init__(self, text, color):
        super().__init__()
        self.setStyleSheet(f"background:{color}18; border:1px solid {color}55; border-radius:10px;")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 9, 16, 9)
        icon = QLabel("〜")
        icon.setStyleSheet(f"color:{color}; font-size:13px; border:none; background:transparent;")
        lay.addWidget(icon)
        lab = QLabel(text)
        lab.setStyleSheet(f"color:{color}; font-size:12.5px; font-weight:500; border:none; background:transparent;")
        lay.addWidget(lab)
        lay.addStretch()


class Mode1Page(QWidget):
    """EMG-Driven Control."""

    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 16, 20, 16)
        outer.setSpacing(14)

        title = QLabel("MODE 1 – EMG-DRIVEN CONTROL")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color:{GREEN}; font-size:17px; font-weight:800; border:none;")
        outer.addWidget(title)

        row = QHBoxLayout()
        row.setSpacing(14)
        outer.addLayout(row, 1)

        # Left: EMG signals
        left = card_frame()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(18, 16, 18, 16)
        ll.setSpacing(4)
        ll.addWidget(section_title("EMG SIGNALS (mV)"))
        specs = [("Channel 1", "0.32 mV", GREEN), ("Channel 2", "0.28 mV", BLUE),
                 ("Channel 3", "0.31 mV", ORANGE), ("Channel 4", "0.29 mV", PURPLE)]
        self.rows = []
        for n, v, c in specs:
            r = ChannelRow(n, v, c)
            ll.addWidget(r)
            self.rows.append(r)
        ll.addStretch()
        rate = QLabel("●  Sampling Rate: 1000 Hz")
        rate.setStyleSheet(f"color:{TEXT_MUTED}; font-size:11px; border:none; background:transparent;")
        ll.addWidget(rate)
        row.addWidget(left, 3)

        # Center: leg + mirroring
        center = card_frame()
        cl = QVBoxLayout(center)
        cl.setContentsMargins(10, 16, 10, 16)
        cl.addStretch()
        leg = LegGraphic(hip_l=BLUE, knee_l=BLUE, hip_r=GREEN, knee_r=GREEN)
        cl.addWidget(leg, alignment=Qt.AlignmentFlag.AlignCenter)
        cl.addStretch()
        mirror = QLabel("‹   MIRRORING MOVEMENT   ›")
        mirror.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mirror.setStyleSheet(f"color:{GREEN}; font-size:12.5px; font-weight:700; border:none; background:transparent;")
        cl.addWidget(mirror)
        row.addWidget(center, 5)

        # Right: assistance status / sub-mode / quick info
        right_col = QVBoxLayout()
        right_col.setSpacing(14)
        right_wrap = QWidget()
        right_wrap.setLayout(right_col)

        assist = card_frame()
        al = QVBoxLayout(assist)
        al.setContentsMargins(18, 14, 18, 14)
        al.addWidget(section_title("ASSISTANCE STATUS"))
        gauge = SemiGauge(65, GREEN, "Assistance Level")
        al.addWidget(gauge)
        torque_row = QHBoxLayout()
        tl = QLabel("Target Torque:")
        tl.setStyleSheet(f"color:{TEXT_MUTED}; font-size:11.5px; border:none; background:transparent;")
        tv = QLabel("Medium")
        tv.setStyleSheet(f"color:{GREEN}; font-size:11.5px; font-weight:700; border:none; background:transparent;")
        torque_row.addWidget(tl)
        torque_row.addWidget(tv)
        torque_row.addStretch()
        al.addLayout(torque_row)
        right_col.addWidget(assist)

        submode = card_frame()
        sl = QVBoxLayout(submode)
        sl.setContentsMargins(18, 14, 18, 14)
        sl.setSpacing(10)
        sl.addWidget(section_title("SUB-MODE"))
        btn_row = QHBoxLayout()
        stand_btn = QPushButton("🧍  STAND")
        walk_btn = QPushButton("🚶  WALK 1-5")
        stand_btn.setCheckable(True)
        walk_btn.setCheckable(True)
        stand_btn.setChecked(True)
        for b in (stand_btn, walk_btn):
            b.setMinimumHeight(36)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
        stand_btn.setStyleSheet(
            f"QPushButton {{ background:{GREEN}22; color:{GREEN}; border:1px solid {GREEN}; border-radius:8px; font-weight:700; font-size:12px; }}"
        )
        walk_btn.setStyleSheet(
            f"QPushButton {{ background:{CARD_BG_2}; color:{TEXT_MUTED}; border:1px solid {BORDER}; border-radius:8px; font-weight:700; font-size:12px; }}"
        )
        btn_row.addWidget(stand_btn)
        btn_row.addWidget(walk_btn)
        sl.addLayout(btn_row)

        wl_row = QHBoxLayout()
        wl_lab = QLabel("WALK LEVEL")
        wl_lab.setStyleSheet(f"color:{TEXT_MUTED}; font-size:11px; border:none; background:transparent;")
        wl_val = QLabel("3 / 5")
        wl_val.setStyleSheet(f"color:{TEXT}; font-size:11.5px; font-weight:700; border:none; background:transparent;")
        wl_row.addWidget(wl_lab)
        wl_row.addStretch()
        wl_row.addWidget(wl_val)
        sl.addLayout(wl_row)

        dots_row = QHBoxLayout()
        minus = QPushButton("−")
        minus.setFixedSize(26, 26)
        plus = QPushButton("+")
        plus.setFixedSize(26, 26)
        for b in (minus, plus):
            b.setStyleSheet(f"QPushButton {{ background:{CARD_BG_2}; color:{TEXT}; border:1px solid {BORDER}; border-radius:6px; }}")
        dots_row.addWidget(minus)
        for i in range(5):
            dot = QFrame()
            dot.setFixedHeight(6)
            dot.setStyleSheet(f"background:{GREEN if i < 3 else BORDER}; border-radius:3px;")
            dots_row.addWidget(dot)
        dots_row.addWidget(plus)
        sl.addLayout(dots_row)
        right_col.addWidget(submode)

        quick = card_frame()
        ql = QVBoxLayout(quick)
        ql.setContentsMargins(18, 14, 18, 14)
        ql.setSpacing(8)
        ql.addWidget(section_title("QUICK INFO"))
        for label, value in (("Step Speed", "0.8 m/s"), ("Step Count", "124"), ("Session Time", "00:02:35")):
            r = QHBoxLayout()
            l = QLabel(label)
            l.setStyleSheet(f"color:{TEXT_MUTED}; font-size:12px; border:none; background:transparent;")
            v = QLabel(value)
            v.setStyleSheet(f"color:{BLUE}; font-size:12px; font-weight:700; border:none; background:transparent;")
            r.addWidget(l)
            r.addStretch()
            r.addWidget(v)
            ql.addLayout(r)
        right_col.addWidget(quick)
        right_col.addStretch()

        row.addWidget(right_wrap, 3)

        outer.addWidget(InfoBar("EMG signals detected. Providing proportional assistance.", GREEN))

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(700)

    def _tick(self):
        for r in self.rows:
            r.spark.tick()
            r.val.setText(f"{r.spark.values[-1]:.2f} mV")


class PostureCard(QFrame):
    clicked_sig = pyqtSignal(str)

    def __init__(self, key, label, selected=False):
        super().__init__()
        self.key = key
        self.selected = selected
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(70)
        self._paint()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        icon = QLabel("🧍")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet("font-size:20px; border:none; background:transparent;")
        lay.addWidget(icon)
        lab = QLabel(label)
        lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lab.setWordWrap(True)
        lab.setStyleSheet(f"color:{TEXT}; font-size:9.5px; font-weight:700; border:none; background:transparent;")
        lay.addWidget(lab)

    def _paint(self):
        if self.selected:
            self.setStyleSheet(f"QFrame {{ background:{BLUE}22; border:1.5px solid {BLUE}; border-radius:10px; }}")
        else:
            self.setStyleSheet(f"QFrame {{ background:{CARD_BG_2}; border:1px solid {BORDER}; border-radius:10px; }}")

    def mousePressEvent(self, e):
        self.clicked_sig.emit(self.key)

    def set_selected(self, val):
        self.selected = val
        self._paint()


class Mode2Page(QWidget):
    """Pre-Programmed Gait."""

    def __init__(self, main_window):
        super().__init__()
        self.main = main_window
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 16, 20, 16)
        outer.setSpacing(14)

        title = QLabel("MODE 2 - PRE-PROGRAMMED POSTURE")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color:{BLUE}; font-size:17px; font-weight:800; border:none;")
        outer.addWidget(title)

        row = QHBoxLayout()
        row.setSpacing(14)
        outer.addLayout(row, 1)

        # Left: posture select
        left = card_frame()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(16, 14, 16, 14)
        ll.setSpacing(10)
        ll.addWidget(section_title("SELECT POSTURE"))
        grid = QGridLayout()
        grid.setSpacing(8)
        DISPLAY_NAMES = {
            "stand_neutral": "STAND (NEUTRAL)",
            "knee_bend": "KNEE BEND",
            "sit_like_bend": "SIT-LIKE BEND",
            "forward_lean": "FORWARD LEAN",
            "backward_lean": "BACKWARD LEAN",
            "step_prepare": "STEP PREPARE",
        }
        postures = [
            "stand_neutral",
            "knee_bend",
            "sit_like_bend",
            "forward_lean",
            "backward_lean",
            "step_prepare",
        ]
        self.posture_cards = []
        self.selected_gait = "KNEE BEND"
        for i, name in enumerate(postures):
            c = PostureCard(name, DISPLAY_NAMES[name], selected=(name == "KNEE BEND"))
            c.clicked_sig.connect(self._select_posture)
            grid.addWidget(c, i // 2, i % 2)
            self.posture_cards.append(c)
        ll.addLayout(grid)
        exec_btn = QPushButton("▶  EXECUTE POSTURE")
        exec_btn.setMinimumHeight(38)
        exec_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        exec_btn.setStyleSheet(
            f"QPushButton {{ background:{BLUE}; color:white; border-radius:9px; font-weight:700; font-size:12.5px; }}"
            f"QPushButton:hover {{ background:#2f6fe0; }}"
        )
        exec_btn.clicked.connect(self.execute_clicked)
        ll.addWidget(exec_btn)
        row.addWidget(left, 3)

        # Center: leg + posture + angle
        center = card_frame()
        cl = QVBoxLayout(center)
        cl.setContentsMargins(10, 16, 10, 10)
        cl.setSpacing(4)
        cur = QLabel("CURRENT POSTURE")
        cur.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cur.setStyleSheet(f"color:{TEXT_MUTED}; font-size:11px; font-weight:600; border:none; background:transparent;")
        cl.addWidget(cur)
        self.posture_name = QLabel("KNEE BEND")
        self.posture_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.posture_name.setStyleSheet(f"color:{BLUE}; font-size:19px; font-weight:800; border:none; background:transparent;")
        cl.addWidget(self.posture_name)
        cl.addStretch()
        legrow = QHBoxLayout()
        legrow.addStretch()
        self.leg = LegGraphic(hip_l=BLUE, knee_l=BLUE, hip_r=BLUE, knee_r=BLUE)
        legrow.addWidget(self.leg)
        angle_col = QVBoxLayout()
        angle_col.addStretch()
        al = QLabel("Knee Angle")
        al.setAlignment(Qt.AlignmentFlag.AlignCenter)
        al.setStyleSheet(f"color:{TEXT_MUTED}; font-size:11px; border:none; background:transparent;")
        self.knee_angle_val_label = QLabel("63°")
        self.knee_angle_val_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.knee_angle_val_label.setStyleSheet(f"color:{BLUE}; font-size:20px; font-weight:800; border:none; background:transparent;")
        angle_col.addWidget(al)
        angle_col.addWidget(self.knee_angle_val_label)
        angle_col.addStretch()
        legrow.addLayout(angle_col)
        legrow.addStretch()
        cl.addLayout(legrow)
        cl.addStretch()

        status_row = QHBoxLayout()
        ms = QLabel("●  Movement Status:")
        ms.setStyleSheet(f"color:{TEXT_MUTED}; font-size:11.5px; border:none; background:transparent;")
        msv = QLabel("Active")
        msv.setStyleSheet(f"color:{GREEN}; font-size:11.5px; font-weight:700; border:none; background:transparent;")
        ex = QLabel("Execution:")
        ex.setStyleSheet(f"color:{TEXT_MUTED}; font-size:11.5px; border:none; background:transparent;")
        exv = QLabel("Running")
        exv.setStyleSheet(f"color:{BLUE}; font-size:11.5px; font-weight:700; border:none; background:transparent;")
        status_row.addStretch()
        status_row.addWidget(ms)
        status_row.addWidget(msv)
        status_row.addSpacing(16)
        status_row.addWidget(ex)
        status_row.addWidget(exv)
        status_row.addStretch()
        cl.addLayout(status_row)
        row.addWidget(center, 5)

        # Right: posture info / joint targets / quick controls
        right_col = QVBoxLayout()
        right_col.setSpacing(14)
        right_wrap = QWidget()
        right_wrap.setLayout(right_col)

        info = card_frame()
        il = QVBoxLayout(info)
        il.setContentsMargins(18, 14, 18, 14)
        il.setSpacing(6)
        il.addWidget(section_title("POSTURE INFORMATION"))
        for label, value, color in (
            ("Posture Name", "Knee Bend", BLUE),
            ("Description", "Bend both knees to a partial squat.", TEXT),
            ("Target Duration", "10 sec", BLUE),
            ("Speed", "Medium", BLUE),
            ("Repetitions", "3 / 5", BLUE),
        ):
            r = QHBoxLayout()
            l = QLabel(label)
            l.setStyleSheet(f"color:{TEXT_MUTED}; font-size:11px; border:none; background:transparent;")
            v = QLabel(value)
            v.setWordWrap(True)
            v.setAlignment(Qt.AlignmentFlag.AlignRight)
            v.setStyleSheet(f"color:{color}; font-size:11px; font-weight:700; border:none; background:transparent;")
            r.addWidget(l)
            r.addStretch()
            r.addWidget(v)
            il.addLayout(r)
        prog_row = QHBoxLayout()
        pl = QLabel("Progress")
        pl.setStyleSheet(f"color:{TEXT_MUTED}; font-size:11px; border:none; background:transparent;")
        prog_row.addWidget(pl)
        prog_row.addWidget(Bar(60, BLUE))
        pv = QLabel("60%")
        pv.setStyleSheet(f"color:{BLUE}; font-size:11px; font-weight:700; border:none; background:transparent;")
        prog_row.addWidget(pv)
        il.addLayout(prog_row)
        right_col.addWidget(info)

        joints = card_frame()
        jl = QVBoxLayout(joints)
        jl.setContentsMargins(18, 14, 18, 14)
        jl.setSpacing(8)
        jl.addWidget(section_title("JOINT TARGET OVERVIEW"))
        for label, value, color in (("Hip (L)", "-12°", GREEN), ("Knee (L)", "63°", BLUE),
                                     ("Hip (R)", "-11°", GREEN), ("Knee (R)", "62°", BLUE)):
            r = QHBoxLayout()
            l = QLabel(label)
            l.setFixedWidth(56)
            l.setStyleSheet(f"color:{TEXT}; font-size:11px; border:none; background:transparent;")
            r.addWidget(l)
            r.addWidget(Bar(abs(float(value.strip("°"))) / 90 * 100, color))
            v = QLabel(value)
            v.setFixedWidth(36)
            v.setAlignment(Qt.AlignmentFlag.AlignRight)
            v.setStyleSheet(f"color:{color}; font-size:11px; font-weight:700; border:none; background:transparent;")
            r.addWidget(v)
            jl.addLayout(r)
        right_col.addWidget(joints)

        quick = card_frame()
        ql = QVBoxLayout(quick)
        ql.setContentsMargins(18, 14, 18, 14)
        ql.setSpacing(8)
        ql.addWidget(section_title("QUICK CONTROLS"))
        btn_row = QHBoxLayout()
        pause_b = QPushButton("⏸ Pause")
        stop_b = QPushButton("■ Stop")
        reset_b = QPushButton("↺ Reset")
        pause_b.setStyleSheet(f"QPushButton {{ background:{ORANGE_BG}; color:{ORANGE}; border:1px solid {ORANGE}55; border-radius:8px; padding:6px; font-weight:600; font-size:11px; }}")
        stop_b.setStyleSheet(f"QPushButton {{ background:{RED_BG}; color:{RED}; border:1px solid {RED}55; border-radius:8px; padding:6px; font-weight:600; font-size:11px; }}")
        reset_b.setStyleSheet(f"QPushButton {{ background:{CARD_BG_2}; color:{TEXT}; border:1px solid {BORDER}; border-radius:8px; padding:6px; font-weight:600; font-size:11px; }}")

        stop_b.clicked.connect(self.stop_clicked)
        for b in (pause_b, stop_b, reset_b):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_row.addWidget(b)
        ql.addLayout(btn_row)
        right_col.addWidget(quick)
        right_col.addStretch()

        row.addWidget(right_wrap, 3)

        # status updates log
        log = card_frame()
        log_lay = QVBoxLayout(log)
        log_lay.setContentsMargins(18, 12, 18, 12)
        log_lay.setSpacing(4)
        log_lay.addWidget(section_title("STATUS UPDATES"))
        for t, msg, color in (
            ("12:45:10", "Posture 'Knee Bend' selected.", BLUE),
            ("12:45:12", "Moving to target position...", BLUE),
            ("12:45:18", "Target position reached. Holding posture.", GREEN),
        ):
            r = QHBoxLayout()
            dot = QLabel("●")
            dot.setStyleSheet(f"color:{color}; font-size:9px; border:none; background:transparent;")
            r.addWidget(dot)
            tl = QLabel(t)
            tl.setStyleSheet(f"color:{TEXT_MUTED}; font-size:11px; border:none; background:transparent;")
            r.addWidget(tl)
            ml = QLabel(msg)
            ml.setStyleSheet(f"color:{TEXT}; font-size:11px; border:none; background:transparent;")
            r.addWidget(ml)
            r.addStretch()
            log_lay.addLayout(r)
        outer.addWidget(log)

    def _select_posture(self, key):
        for c in self.posture_cards:
            c.set_selected(c.key == key)
        self.posture_name.setText(key)

        self.selected_gait = key
        self.posture_name.setText(key)
    
    def execute_clicked(self):
        self.main.start_gait(
            self.selected_gait
        )

    def set_joint_angles(self, left_hip, left_knee, right_hip, right_knee):
        self.leg.hip_angle_l = left_hip
        self.leg.knee_angle_l = left_knee
        self.leg.hip_angle_r = right_hip
        self.leg.knee_angle_r = right_knee
        self.leg.update()
        if hasattr(self, 'knee_angle_val_label'):
            self.knee_angle_val_label.setText(f"{int(abs(left_knee))}°")
    
    def on_motor_feedback(self, left_hip, left_knee, right_hip, right_knee):
        self.leg.hip_angle_l = left_hip
        self.leg.knee_angle_l = left_knee
        self.leg.hip_angle_r = right_hip
        self.leg.knee_angle_r = right_knee

        self.leg.update()
    
    def stop_clicked(self):
        self.main.stop_gait()


class SliderRow(QWidget):
    def __init__(self, label, value, color, suffix="%"):
        super().__init__()
        self.suffix = suffix
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 6, 0, 6)
        lay.setSpacing(4)
        top = QHBoxLayout()
        l = QLabel(label)
        l.setStyleSheet(f"color:{color}; font-size:12px; font-weight:700; border:none; background:transparent;")
        top.addWidget(l)
        top.addStretch()
        lay.addLayout(top)

        row = QHBoxLayout()
        row.setSpacing(8)
        minus = QPushButton("−")
        plus = QPushButton("+")
        for b in (minus, plus):
            b.setFixedSize(24, 24)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(f"QPushButton {{ background:{CARD_BG_2}; color:{TEXT}; border:1px solid {BORDER}; border-radius:6px; }}")
        row.addWidget(minus)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setValue(value)
        self.slider.setStyleSheet(
            f"""
            QSlider::groove:horizontal {{ height:6px; background:{BORDER}; border-radius:3px; }}
            QSlider::sub-page:horizontal {{ background:{color}; border-radius:3px; }}
            QSlider::handle:horizontal {{ background:white; border:2px solid {color}; width:16px; margin:-6px 0; border-radius:8px; }}
            """
        )
        row.addWidget(self.slider, 1)
        row.addWidget(plus)

        self.value_label = QLabel(f"{value}{self.suffix}")
        self.value_label.setFixedWidth(42)
        self.value_label.setStyleSheet(f"color:{color}; font-size:14px; font-weight:800; border:none; background:transparent;")
        row.addWidget(self.value_label)
        lay.addLayout(row)

        self.scale_labels = []
        scale_row = QHBoxLayout()
        for i in range(3):
            sl = QLabel("")
            sl.setStyleSheet(f"color:{TEXT_DIM}; font-size:9.5px; border:none; background:transparent;")
            scale_row.addWidget(sl)
            self.scale_labels.append(sl)
            if i < 2:
                scale_row.addStretch()
        lay.addLayout(scale_row)

        self.update_scale_labels()

        minus.clicked.connect(lambda: self.slider.setValue(max(self.slider.minimum(), self.slider.value() - 5)))
        plus.clicked.connect(lambda: self.slider.setValue(min(self.slider.maximum(), self.slider.value() + 5)))
        self.slider.valueChanged.connect(lambda v: self.value_label.setText(f"{v}{self.suffix}"))

    def update_scale_labels(self):
        min_v = self.slider.minimum()
        max_v = self.slider.maximum()
        mid_v = (min_v + max_v) // 2
        if len(self.scale_labels) == 3:
            self.scale_labels[0].setText(f"{min_v}{self.suffix}")
            self.scale_labels[1].setText(f"{mid_v}{self.suffix}")
            self.scale_labels[2].setText(f"{max_v}{self.suffix}")

    def set_range(self, min_v, max_v, suffix="°"):
        self.suffix = suffix
        self.slider.setRange(min_v, max_v)
        self.update_scale_labels()
        self.value_label.setText(f"{self.slider.value()}{self.suffix}")


class Mode3Page(QWidget):
    """Impedance Control (Manual)."""

    def __init__(self, main_window):
        super().__init__()
        self.main = main_window

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 16, 20, 16)
        outer.setSpacing(14)

        title = QLabel("MODE 3 – IMPEDANCE CONTROL (MANUAL)")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color:{PURPLE}; font-size:17px; font-weight:800; border:none;")
        outer.addWidget(title)
        sub = QLabel("Assist / Resist Control")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet(f"color:{TEXT_MUTED}; font-size:11.5px; border:none;")
        outer.addWidget(sub)

        row = QHBoxLayout()
        row.setSpacing(14)
        outer.addLayout(row, 1)

        # Left: exoskeleton status
        left = card_frame()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(16, 14, 16, 14)
        ll.setSpacing(8)
        ll.addWidget(section_title("🦾  EXOSKELETON STATUS"))
        joint_specs = [
            ("Hip Left (Thigh A)", "28°", "61%", GREEN),
            ("Knee Left (Knee B)", "-47°", "42%", BLUE),
            ("Hip Right (Thigh C)", "22°", "38%", PURPLE),
            ("Knee Right (Knee D)", "-55°", "59%", ORANGE),
        ]
        self.status_labels = []
        for name, angle, pct, color in joint_specs:
            r = QFrame()
            rl = QHBoxLayout(r)
            rl.setContentsMargins(0, 4, 0, 4)
            icon = QLabel("🔑")
            icon.setStyleSheet(f"color:{color}; font-size:12px; border:none; background:transparent;")
            rl.addWidget(icon)
            col = QVBoxLayout()
            col.setSpacing(0)
            nlab = QLabel(name)
            nlab.setStyleSheet(f"color:{TEXT}; font-size:11px; font-weight:600; border:none; background:transparent;")
            alab = QLabel(f"Angle: {angle}")
            alab.setStyleSheet(f"color:{TEXT_MUTED}; font-size:10px; border:none; background:transparent;")
            col.addWidget(nlab)
            col.addWidget(alab)
            rl.addLayout(col)
            rl.addStretch()
            plab = QLabel(pct)
            plab.setStyleSheet(f"color:{color}; font-size:13px; font-weight:800; border:none; background:transparent;")
            rl.addWidget(plab)
            ll.addWidget(r)
            self.status_labels.append({
                'angle': alab,
                'pct': plab
            })

        legend = QFrame()
        leg_lay = QVBoxLayout(legend)
        leg_lay.setContentsMargins(0, 8, 0, 0)
        leg_lay.setSpacing(4)
        for name, color in (("Thigh A (Left)", GREEN), ("Knee B (Left)", BLUE),
                             ("Thigh C (Right)", PURPLE), ("Knee D (Right)", ORANGE)):
            r = QHBoxLayout()
            dot = QLabel("●")
            dot.setStyleSheet(f"color:{color}; font-size:10px; border:none; background:transparent;")
            r.addWidget(dot)
            t = QLabel(name)
            t.setStyleSheet(f"color:{TEXT_MUTED}; font-size:10.5px; border:none; background:transparent;")
            r.addWidget(t)
            r.addStretch()
            leg_lay.addLayout(r)
        ll.addWidget(legend)
        ll.addStretch()
        row.addWidget(left, 3)

        # Center: leg graphic
        center = card_frame()
        cl = QVBoxLayout(center)
        cl.setContentsMargins(10, 16, 10, 16)
        cl.addStretch()
        self.leg = LegGraphic(hip_l=GREEN, knee_l=BLUE, hip_r=PURPLE, knee_r=ORANGE)
        self.leg.hip_angle_l = 28
        self.leg.knee_angle_l = -47
        self.leg.hip_angle_r = 22
        self.leg.knee_angle_r = -55
        cl.addWidget(self.leg, alignment=Qt.AlignmentFlag.AlignCenter)
        cl.addStretch()
        row.addWidget(center, 4)

        # Right: control mode + manual joint control
        right_col = QVBoxLayout()
        right_col.setSpacing(14)
        right_wrap = QWidget()
        right_wrap.setLayout(right_col)

        ctrl = card_frame()
        cml = QVBoxLayout(ctrl)
        cml.setContentsMargins(18, 14, 18, 14)
        cml.setSpacing(8)
        cml.addWidget(section_title("CONTROL MODE"))
        sm_lab = QLabel("Sub-Mode")
        sm_lab.setStyleSheet(f"color:{TEXT_MUTED}; font-size:11px; border:none; background:transparent;")
        cml.addWidget(sm_lab)
        cml.addWidget(pill("ASSISTANCE", PURPLE, PURPLE_BG))
        for label, value, color in (("Target", "Medium Assist", PURPLE), ("System Response", "Smooth", TEXT)):
            l = QLabel(label)
            l.setStyleSheet(f"color:{TEXT_MUTED}; font-size:10.5px; border:none; background:transparent; margin-top:4px;")
            v = QLabel(value)
            v.setStyleSheet(f"color:{color}; font-size:12.5px; font-weight:700; border:none; background:transparent;")
            cml.addWidget(l)
            cml.addWidget(v)
        il = QLabel("Impedance Level")
        il.setStyleSheet(f"color:{TEXT_MUTED}; font-size:10.5px; border:none; background:transparent; margin-top:4px;")
        cml.addWidget(il)
        iv_row = QHBoxLayout()
        iv = QLabel("65%")
        iv.setStyleSheet(f"color:{PURPLE}; font-size:13px; font-weight:800; border:none; background:transparent;")
        iv_row.addWidget(iv)
        cml.addLayout(iv_row)
        cml.addWidget(Bar(65, PURPLE))
        mv_row = QHBoxLayout()
        mv_l = QLabel("Movement Status")
        mv_l.setStyleSheet(f"color:{TEXT_MUTED}; font-size:10.5px; border:none; background:transparent; margin-top:6px;")
        cml.addWidget(mv_l)
        mv_v = QLabel("●  Active")
        mv_v.setStyleSheet(f"color:{GREEN}; font-size:11.5px; font-weight:700; border:none; background:transparent;")
        cml.addWidget(mv_v)
        right_col.addWidget(ctrl)
        right_col.addStretch()
        row.addWidget(right_wrap, 3)

        # Manual joint control panel (full width under the row)
        manual = card_frame()
        ml = QVBoxLayout(manual)
        ml.setContentsMargins(20, 16, 20, 16)
        ml.setSpacing(4)
        ml.addWidget(section_title("MANUAL JOINT CONTROL"))
        hint = QLabel("Adjust each joint assistance level")
        hint.setStyleSheet(f"color:{TEXT_MUTED}; font-size:11px; border:none; background:transparent;")
        ml.addWidget(hint)
        sliders_row = QHBoxLayout()
        sliders_row.setSpacing(20)
        self.sliders = []
        for label, value, color in (
            ("Motor 2 – Thigh A (Left)", 28, GREEN),
            ("Motor 3 – Knee B (Left)", -47, BLUE),
            ("Motor 4 – Thigh C (Right)", 22, PURPLE),
            ("Motor 5 – Knee D (Right)", -55, ORANGE),
        ):
            s = SliderRow(label, value, color)
            sliders_row.addWidget(s)
            self.sliders.append(s)

        # Left Hip
        self.sliders[0].set_range(0, 90, "°")
        self.sliders[0].slider.valueChanged.connect(
            lambda v: (
                self.update_joint_ui(0, v),
                self.update_robot()
            )
        )

        # Left Knee
        self.sliders[1].set_range(-90, 0, "°")
        self.sliders[1].slider.valueChanged.connect(
            lambda v: (
                self.update_joint_ui(1, v),
                self.update_robot()
            )
        )

        # Right Hip
        self.sliders[2].set_range(0, 90, "°")
        self.sliders[2].slider.valueChanged.connect(
            lambda v: (
                self.update_joint_ui(2, v),
                self.update_robot()
            )
        )

        # Right Knee
        self.sliders[3].set_range(-90, 0, "°")
        self.sliders[3].slider.valueChanged.connect(
            lambda v: (
                self.update_joint_ui(3, v),
                self.update_robot()
            )
        )

        ml.addLayout(sliders_row)

        note = QLabel("ⓘ  0% = Minimum Assistance (Least Effort)     100% = Maximum Assistance (Most Effort)")
        note.setStyleSheet(f"color:{TEXT_MUTED}; font-size:10.5px; border:none; background:transparent; margin-top:6px;")
        ml.addWidget(note)
        outer.addWidget(manual)

        # bottom row: overall assist / realtime / safety / quick actions
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(14)

        overall = card_frame()
        ol = QVBoxLayout(overall)
        ol.setContentsMargins(14, 10, 14, 10)
        ol.addWidget(section_title("Overall Assistance Level", TEXT_MUTED))
        ol.addWidget(SemiGauge(50, PURPLE, "Medium"))
        bottom_row.addWidget(overall, 2)

        rt = card_frame()
        rl2 = QVBoxLayout(rt)
        rl2.setContentsMargins(14, 12, 14, 12)
        head = QHBoxLayout()
        head.addWidget(section_title("Real-time Updates", TEXT_MUTED))
        head.addStretch()
        live = QLabel("●  Live")
        live.setStyleSheet(f"color:{GREEN}; font-size:10.5px; font-weight:700; border:none; background:transparent;")
        head.addWidget(live)
        rl2.addLayout(head)
        self.rt_spark = Sparkline(PURPLE, points=30)
        rl2.addWidget(self.rt_spark)
        bottom_row.addWidget(rt, 3)

        safety = card_frame()
        sfl = QVBoxLayout(safety)
        sfl.setContentsMargins(14, 12, 14, 12)
        sfl.addWidget(section_title("Safety Status", TEXT_MUTED))
        sv = QLabel("🛡  OK")
        sv.setStyleSheet(f"color:{GREEN}; font-size:15px; font-weight:800; border:none; background:transparent;")
        sfl.addWidget(sv)
        sd = QLabel("●  All Systems Normal")
        sd.setStyleSheet(f"color:{TEXT_MUTED}; font-size:10.5px; border:none; background:transparent;")
        sfl.addWidget(sd)
        bottom_row.addWidget(safety, 2)

        quick = card_frame()
        ql = QVBoxLayout(quick)
        ql.setContentsMargins(14, 12, 14, 12)
        ql.addWidget(section_title("QUICK ACTIONS", TEXT_MUTED))
        qrow = QHBoxLayout()
        home_b = QPushButton("⌂ Home Position")
        reset_b = QPushButton("↺ Reset All")
        stop_b = QPushButton("■ Stop Motion")
        home_b.setStyleSheet(f"QPushButton {{ background:{BLUE_BG}; color:{BLUE}; border:1px solid {BLUE}55; border-radius:8px; padding:6px; font-weight:600; font-size:10.5px; }}")
        reset_b.setStyleSheet(f"QPushButton {{ background:{ORANGE_BG}; color:{ORANGE}; border:1px solid {ORANGE}55; border-radius:8px; padding:6px; font-weight:600; font-size:10.5px; }}")
        stop_b.setStyleSheet(f"QPushButton {{ background:{RED_BG}; color:{RED}; border:1px solid {RED}55; border-radius:8px; padding:6px; font-weight:600; font-size:10.5px; }}")
        for b in (home_b, reset_b, stop_b):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            qrow.addWidget(b)
        ql.addLayout(qrow)
        bottom_row.addWidget(quick, 3)

        outer.addLayout(bottom_row)

        self.timer = QTimer(self)
        self.timer.timeout.connect(lambda: self.rt_spark.tick())
        self.timer.start(600)
    
    def update_robot(self):
        self.leg.update()
        self.main.publish_joint_state(
            self.leg.hip_angle_l,
            self.leg.knee_angle_l,
            self.leg.hip_angle_r,
            self.leg.knee_angle_r,
        )
        self.main.publish_motor_angles(
            self.leg.hip_angle_l,
            self.leg.knee_angle_l,
            self.leg.hip_angle_r,
            self.leg.knee_angle_r,
        )

    def update_joint_ui(self, index, value):
        def value_to_color(v):
            if v > 66:
                return GREEN
            elif v > 33:
                return ORANGE
            else:
                return RED

        color = value_to_color(abs(value))

        if index == 0:
            self.leg.hip_angle_l = value
            self.leg.hip_l = color
        elif index == 1:
            self.leg.knee_angle_l = value
            self.leg.knee_l = color
        elif index == 2:
            self.leg.hip_angle_r = value
            self.leg.hip_r = color
        elif index == 3:
            self.leg.knee_angle_r = value
            self.leg.knee_r = color

        self.leg.update()

        if hasattr(self, 'status_labels') and index < len(self.status_labels):
            self.status_labels[index]['angle'].setText(f"Angle: {int(value)}°")
            self.status_labels[index]['pct'].setText(f"{int(abs(value) / 90 * 100)}%")
            self.status_labels[index]['pct'].setStyleSheet(
                f"color:{color}; font-size:13px; font-weight:800; border:none; background:transparent;"
            )

    def set_joint_angles(self, left_hip, left_knee, right_hip, right_knee):
        values = [left_hip, left_knee, right_hip, right_knee]

        # Update sliders WITHOUT emitting valueChanged to avoid loops
        for i, (slider_row, value) in enumerate(zip(self.sliders, values)):
            slider_row.slider.blockSignals(True)
            slider_row.slider.setValue(int(value))
            slider_row.slider.blockSignals(False)
            slider_row.value_label.setText(f"{int(value)}{slider_row.suffix}")
            
            # Sync the graphics, colors, and status panel values
            self.update_joint_ui(i, value)



class PlaceholderPage(QWidget):
    def __init__(self, title):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        panel = card_frame()
        pl = QVBoxLayout(panel)
        pl.setContentsMargins(30, 60, 30, 60)
        t = QLabel(title)
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        t.setStyleSheet(f"color:{TEXT}; font-size:18px; font-weight:700; border:none;")
        sub = QLabel("This section is coming soon.")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet(f"color:{TEXT_MUTED}; font-size:12.5px; border:none;")
        pl.addWidget(t)
        pl.addWidget(sub)
        lay.addWidget(panel)


# ----------------------------------------------------------------------
# Main window
# ----------------------------------------------------------------------
MODE_INFO = {
    0: dict(number=None, name="Not Selected", sub="", color=TEXT, bottom="System ready.", bottom_color=TEXT_MUTED, third="conn"),
    1: dict(number=1, name="EMG-Driven Control", sub="Voluntary Control", color=GREEN,
            bottom="EMG signals detected. Providing proportional assistance.", bottom_color=GREEN, third="emg"),
    2: dict(number=2, name="Pre-Programmed Gait", sub="Automatic Gait Patterns", color=BLUE,
            bottom="Executing posture 'Knee Bend'.", bottom_color=BLUE, third="emg"),
    3: dict(number=3, name="Impedance Control", sub="ASSIST / RESIST", color=PURPLE,
            bottom="Impedance control active. Adjust sliders to change assistance/resistance on each joint.",
            bottom_color=PURPLE, third="emg"),
    4: dict(number=None, name="Not Selected", sub="", color=TEXT, bottom="Configure system parameters.", bottom_color=TEXT_MUTED, third="conn"),
    5: dict(number=None, name="Not Selected", sub="", color=TEXT, bottom="Running diagnostics.", bottom_color=TEXT_MUTED, third="conn"),
}


class MainWindow(QWidget):
    def __init__(self, joint_node):
        super().__init__()
        self.ros = joint_node

        self.setWindowFlag(Qt.WindowType.FramelessWindowHint)
        self.resize(1536, 1024)
        self.setStyleSheet(f"background:{BG};")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        outer.addWidget(TitleBar(self))

        self.status_strip = StatusStrip()
        strip_wrap = QFrame()
        strip_wrap.setStyleSheet(f"background:{TOPBAR_BG}; border-bottom:1px solid {BORDER};")
        strip_lay = QVBoxLayout(strip_wrap)
        strip_lay.setContentsMargins(20, 12, 20, 12)
        strip_lay.addWidget(self.status_strip)
        outer.addWidget(strip_wrap)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        outer.addLayout(body, 1)

        self.sidebar = Sidebar()
        self.sidebar.navigate.connect(self.go_to)
        body.addWidget(self.sidebar)

        content_wrap = QWidget()
        content_wrap.setStyleSheet(f"background:{BG};")
        content_lay = QVBoxLayout(content_wrap)
        content_lay.setContentsMargins(0, 0, 0, 0)
        body.addWidget(content_wrap, 1)

        self.stack = QStackedWidget()
        content_lay.addWidget(self.stack)

        self.home_page = HomePage()
        self.home_page.request_nav.connect(self.go_to)
        self.mode1_page = Mode1Page()
        self.mode2_page = Mode2Page(self)
        self.mode3_page = Mode3Page(self)
        self.params_page = PlaceholderPage("PARAMETERS")
        self.diag_page = PlaceholderPage("DIAGNOSTICS")

        for p in (self.home_page, self.mode1_page, self.mode2_page, self.mode3_page,
                  self.params_page, self.diag_page):
            self.stack.addWidget(p)

        self.bottom_bar = BottomBar()
        outer.addWidget(self.bottom_bar)

        self.go_to(0)

    def go_to(self, index):
        self.stack.setCurrentIndex(index)
        self.sidebar.select(index)
        info = MODE_INFO[index]
        self.status_strip.mode_card.set_mode(info["number"], info["name"], info["sub"], info["color"])
        self.status_strip.set_third_card(info["third"])
        self.bottom_bar.set_message(info["bottom"], info["bottom_color"])
    
    def publish_joint_state(self, left_hip, left_knee, right_hip, right_knee):
        self.ros.publish_joint_state(left_hip, left_knee, right_hip, right_knee)
    
    def publish_motor_angles(self, left_hip, left_knee, right_hip, right_knee):
        self.ros.publish_motor_angles(left_hip, left_knee, right_hip, right_knee)
    
    def on_joint_state(self, left_hip, left_knee, right_hip, right_knee):
        self.mode2_page.set_joint_angles(
            left_hip,
            left_knee,
            right_hip,
            right_knee
        )

        self.mode3_page.set_joint_angles(
            left_hip,
            left_knee,
            right_hip,
            right_knee
        )
    
    def on_motor_feedback(self, left_hip, left_knee, right_hip, right_knee):
        if hasattr(self.mode2_page, "on_motor_feedback"):
            self.mode2_page.on_motor_feedback(left_hip, left_knee, right_hip, right_knee)
        if hasattr(self.mode3_page, "on_motor_feedback"):
            self.mode3_page.on_motor_feedback(left_hip, left_knee, right_hip, right_knee)
        
    def start_gait(self, gait_name, repeats=5, hold_time=2.0):
        self.ros.start_gait(gait_name, repeats, hold_time)

    def stop_gait(self):
        self.ros.stop_gait()


def main():
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))

    rclpy.init()
    ros_node = JointStateNode()

    win = MainWindow(ros_node)
    ros_node.gui = win
    win.show()
    
    ros_timer = QTimer()
    ros_timer.timeout.connect(
        lambda: (
        rclpy.spin_once(ros_node, timeout_sec=0.0),
        )
    )
    ros_timer.start(10)
    exit_code = app.exec()

    ros_node.destroy_node()
    rclpy.shutdown()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()