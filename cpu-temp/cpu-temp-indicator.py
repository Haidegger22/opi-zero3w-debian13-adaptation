#!/usr/bin/env python3
"""
cpu-temp-indicator.py — температура CPU в трее MATE (адаптация cpu-temperature-panel
для MATE: репозиторий использует genmon XFCE, которого в MATE нет → AppIndicator).
Обновление каждые 5 сек, чтение /sys/class/thermal/thermal_zone0/temp.
"""
import gi
gi.require_version("AyatanaAppIndicator3", "0.1")
from gi.repository import AyatanaAppIndicator3 as AppIndicator
from gi.repository import GLib

import os

TEMP_SENSOR = "/sys/class/thermal/thermal_zone0/temp"
UPDATE_SEC = 5

ind = AppIndicator.Indicator.new(
    "cpu-temp",
    "utilities-system-monitor",
    AppIndicator.IndicatorCategory.HARDWARE,
)
ind.set_status(AppIndicator.IndicatorStatus.ACTIVE)


def read_temp():
    try:
        with open(TEMP_SENSOR) as f:
            return int(f.read().strip()) // 1000
    except Exception:
        return -1


def update(_=None):
    t = read_temp()
    if t >= 0:
        ind.set_label(f"🌡 {t}°C", "")
    return True  # продолжать таймер


update()
GLib.timeout_add_seconds(UPDATE_SEC, update)
GLib.MainLoop().run()
