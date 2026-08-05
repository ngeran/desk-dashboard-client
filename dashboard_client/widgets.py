"""Small custom-painted widgets for the dashboard.

Both are pure QPainter — no QSS, no filled backgrounds — kept deliberately
minimal so they read as *content* (a live signal, a data value) rather than
decorative chrome. That distinction matters on an always-on OLED panel: we
only want to light pixels that are telling the user something.
"""
from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QRectF,
    Qt,
    Property,
)
from PySide6.QtGui import QColor, QLinearGradient, QPainter
from PySide6.QtWidgets import QWidget


class PulseDot(QWidget):
    """A small circle that breathes (35% → 100% opacity) to signal "live".

    Static color = static state (degraded/disconnected). Breathing = actively
    receiving frames. It's a tiny thing, but it's the difference between a
    status label you have to read and one you register peripherally.
    """

    def __init__(self, color: str, diameter: int = 8) -> None:
        super().__init__()
        self._color = QColor(color)
        self._opacity = 1.0
        self.setFixedSize(diameter, diameter)
        self._anim = QPropertyAnimation(self, b"dotOpacity", self)
        self._anim.setDuration(1400)
        self._anim.setStartValue(0.35)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._anim.setLoopCount(-1)

    def set_color(self, color: str) -> None:
        self._color = QColor(color)
        self.update()

    def set_active(self, active: bool) -> None:
        if active:
            if self._anim.state() != QPropertyAnimation.State.Running:
                self._anim.start()
        else:
            self._anim.stop()
            self._opacity = 1.0
            self.update()

    def _get_opacity(self) -> float:
        return self._opacity

    def _set_opacity(self, value: float) -> None:
        self._opacity = value
        self.update()

    dotOpacity = Property(float, _get_opacity, _set_opacity)

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt override)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(self._color)
        color.setAlphaF(self._opacity)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(self.rect())


class DayProgressBar(QWidget):
    """A hairline gradient bar showing how much of the current day has elapsed.

    Purely ambient — the kind of thing you don't consciously read but that
    makes a static clock feel like it's actually tracking time, not just
    displaying it.
    """

    def __init__(self, color: str, track: str = "#141414", height: int = 3) -> None:
        super().__init__()
        self._color = QColor(color)
        self._track = QColor(track)
        self._fraction = 0.0
        self.setFixedHeight(height)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def set_fraction(self, fraction: float) -> None:
        fraction = max(0.0, min(1.0, fraction))
        if abs(fraction - self._fraction) < 0.0005:
            return
        self._fraction = fraction
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt override)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        radius = rect.height() / 2

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._track)
        painter.drawRoundedRect(rect, radius, radius)

        if self._fraction <= 0:
            return
        fill = QRectF(rect.x(), rect.y(), rect.width() * self._fraction, rect.height())
        gradient = QLinearGradient(fill.topLeft(), fill.topRight())
        gradient.setColorAt(0.0, self._color.darker(150))
        gradient.setColorAt(1.0, self._color)
        painter.setBrush(gradient)
        painter.drawRoundedRect(fill, radius, radius)
