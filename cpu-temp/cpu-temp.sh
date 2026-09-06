#!/bin/bash
TEMP=$(( $(cat /sys/class/thermal/thermal_zone0/temp) / 1000 ))
echo "<txt>🌡 $TEMP°C</txt>"
