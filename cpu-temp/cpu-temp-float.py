#!/usr/bin/env python3
"""
cpu-temp-float.py — плавающий виджет температуры CPU на рабочем столе.
Полупрозрачный, поверх всех окон, перетаскивается мышью (средняя/левая
кнопка за окно), обновление каждые 5 сек. Рисуется градусник через Cairo.
"""
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk, GLib
import cairo
import math

TEMP_SENSOR = "/sys/class/thermal/thermal_zone0/temp"
UPDATE_SEC = 5
W, H = 84, 44

def read_temp():
    try:
        with open(TEMP_SENSOR) as f:
            return int(f.read().strip()) // 1000
    except Exception:
        return -1

class TempFloat(Gtk.Window):
    def __init__(self):
        super().__init__(type=Gtk.WindowType.POPUP)
        self.set_title("cpu-temp")
        self.set_default_size(W, H)
        self.set_resizable(False)
        self.set_decorated(False)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_keep_above(True)
        self.set_app_paintable(True)
        self.set_accept_focus(False)

        # прозрачный фон
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual:
            self.set_visual(visual)
        self.set_position(Gtk.WindowPosition.NONE)
        # стартовая позиция — правый нижний угол
        mw = screen.get_width()
        mh = screen.get_height()
        self.move(mw - W - 16, mh - H - 20)  # 16px от края, 20px над нижней кромкой

        self._temp = 0
        self._drag = None  # (start_x, start_y, win_x, win_y)

        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK |
                        Gdk.EventMask.BUTTON_RELEASE_MASK |
                        Gdk.EventMask.POINTER_MOTION_MASK |
                        Gdk.EventMask.SCROLL_MASK)
        self.connect("draw", self.on_draw)
        self.connect("button-press-event", self.on_press)
        self.connect("button-release-event", self.on_release)
        self.connect("motion-notify-event", self.on_motion)
        self.connect("scroll-event", self.on_scroll)
        # средний клик — закрыть
        self.connect("destroy", Gtk.main_quit)

        self.update_temp()
        GLib.timeout_add_seconds(UPDATE_SEC, self.update_temp)

    def update_temp(self):
        t = read_temp()
        if t >= 0:
            self._temp = t
            self.queue_draw()
        return True

    def on_draw(self, wid, cr):
        # прозрачный фон
        cr.set_source_rgba(0, 0, 0, 0)
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.paint()

        # полупрозрачный тёмный скруглённый фон
        cr.set_operator(cairo.OPERATOR_OVER)
        cr.set_source_rgba(0.08, 0.09, 0.12, 0.72)
        r = 10
        cr.move_to(r, 0)
        cr.line_to(W - r, 0)
        cr.arc(W - r, r, r, -math.pi/2, 0)
        cr.line_to(W, H - r)
        cr.arc(W - r, H - r, r, 0, math.pi/2)
        cr.line_to(r, H)
        cr.arc(r, H - r, r, math.pi/2, math.pi)
        cr.line_to(0, r)
        cr.arc(r, r, r, math.pi, 3*math.pi/2)
        cr.fill()

        t = self._temp
        # цвет по температуре
        if t < 50:
            rc, gc, bc = 0.35, 0.85, 0.35   # зелёный
        elif t < 70:
            rc, gc, bc = 1.0, 0.72, 0.15    # жёлтый
        else:
            rc, gc, bc = 1.0, 0.25, 0.25    # красный

        # --- градусник слева ---
        # колба
        cx, by, br = 22, H - 8, 7
        cr.set_source_rgb(rc, gc, bc)
        cr.arc(cx, by, br, 0, 2*math.pi)
        cr.fill()
        # палочка
        cr.set_source_rgb(0.85, 0.85, 0.88)
        cr.set_line_width(4)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.move_to(cx, by - br)
        cr.line_to(cx, 7)
        cr.stroke()
        # ртуть внутри палочки
        fill_h = max(0, min(t, 95)) / 95.0 * (by - br - 9)
        cr.set_source_rgb(rc, gc, bc)
        cr.set_line_width(2)
        cr.move_to(cx, by - br)
        cr.line_to(cx, by - br - fill_h)
        cr.stroke()

        # --- текст температуры справа ---
        cr.set_font_size(19)
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL,
                            cairo.FONT_WEIGHT_BOLD)
        txt = f"{t}°"
        xb = cr.text_extents(txt)
        tx = W - xb.width - 6
        ty = (H + xb.height/2) / 2 + 2
        # обводка
        cr.set_source_rgb(0, 0, 0)
        cr.set_line_width(3)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)
        cr.move_to(tx, ty)
        cr.text_path(txt)
        cr.stroke()
        # текст белый
        cr.set_source_rgb(1, 1, 1)
        cr.move_to(tx, ty)
        cr.show_text(txt)
        return False

    def on_press(self, w, ev):
        if ev.button == 2:  # средняя — закрыть
            self.destroy()
            return True
        if ev.button == 1 or ev.button == 3:
            wx, wy = self.get_position()
            self._drag = (ev.x_root, ev.y_root, wx, wy)
            return True
        return False

    def on_release(self, w, ev):
        self._drag = None
        return False

    def on_motion(self, w, ev):
        if self._drag:
            sx, sy, wx, wy = self._drag
            self.move(wx + (ev.x_root - sx), wy + (ev.y_root - sy))
            return True
        return False

    def on_scroll(self, w, ev):
        # перемещение колесом — тоже двигаем
        if self._drag is None:
            self._drag = (ev.x_root, ev.y_root,
                          self.get_position()[0], self.get_position()[1])
        return False


if __name__ == "__main__":
    win = TempFloat()
    win.show_all()
    Gtk.main()
