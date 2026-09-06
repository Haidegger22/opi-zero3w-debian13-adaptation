# OPi Zero 3W — адаптация репозиториев под Debian 13 (trixie)

> Готовые, проверенные изменения для переноса старых репозиториев Orange Pi Zero 3W
> с Debian 11 (bullseye) на **Debian 13 (trixie)**.
> Всё проверено на практике: ядро **6.6.98-sun60iw2**, MATE desktop.

## Проблема

Репозитории для Zero 3W писались под Debian 11 (XFCE, RetroArch 1.14, libgpiod v1).
На Debian 13 часть зависимостей и API поменялась — скрипты ломаются.

## Что и зачем менялось

| Репозиторий | Что сломалось на Debian 13 | Решение |
|---|---|---|
| `opi-zero3w-retroarch` | libgpiod v1 API → v2 (python3-libgpiod 2.2.0) | переписаны GPIO-блоки (`request_lines`/`LineSettings`) |
| `opi-zero3w-retroarch` | видео-драйвер `xvideo` исчез из RetroArch 1.20 | замена на `vulkan` — аппаратный PowerVR! |
| `opi-zero3w-retroarch` | путь ядра mGBA в скрипте указывал в `~/.config/retroarch/cores/` | исправлен на системный `/usr/lib/aarch64-linux-gnu/libretro/` |
| `orangepi-zero3w-cpu-temperature-panel` | репозиторий писан под XFCE-genmon, а DE теперь MATE (genmon в MATE нет) | индикатор в трее через AppIndicator |
| `orangepi-zero3w-bluetooth-hid` | — (ядро то же 6.6.98-sun60iw2, `uhid.ko` подошёл) | без изменений, см. заметку |
| `orangepi-zero3w-chromium-russian` / `chromium-cache-ram` | — (пути/сервисы совпали) | без изменений |

---

## 🎮 RetroArch — главные правки

### 1. libgpiod v1 → v2 (Debian 13: python3-libgpiod 2.2.0)

**Было (v1, Debian 11):**
```python
import gpiod
chip = gpiod.Chip('gpiochip0')
lines = chip.get_lines([96, 131])
lines.request(consumer='game-input', type=gpiod.LINE_REQ_DIR_IN,
              flags=gpiod.LINE_REQ_FLAG_BIAS_PULL_UP)
vals = lines.get_values()          # [0, 1] — числа
pressed = (v == 0)
```

**Стало (v2, Debian 13):**
```python
import gpiod
from gpiod.line import Direction, Bias, Value
req = gpiod.request_lines('/dev/gpiochip0', consumer='game-input',
    config={96: gpiod.LineSettings(direction=Direction.INPUT, bias=Bias.PULL_UP),
            131: gpiod.LineSettings(direction=Direction.INPUT, bias=Bias.PULL_UP)})
v = req.get_value(96)              # Value.ACTIVE / Value.INACTIVE — enum!
pressed = (v == Value.INACTIVE)
```

Ключевые отличия:
- `gpiod.Chip(...).get_lines(...).request(...)` → `gpiod.request_lines(..., config={offset: LineSettings(...)})`
- константы `LINE_REQ_DIR_IN` / `LINE_REQ_FLAG_BIAS_PULL_UP` → `Direction.INPUT` / `Bias.PULL_UP`
- `get_values()` возвращает **enum** `Value.ACTIVE/INACTIVE`, а не `0/1` — сравнение с числом ломается
- путь: `/dev/gpiochip0` (не `gpiochip0`)

Затронутые файлы: `scripts/game_input.py`, `scripts/mario_buttons.py`.

### 2. Видео-драйвер: xvideo → vulkan (аппаратный!)

RetroArch в trixie (1.20) собран **без драйвера `xvideo`**. Доступны: `vulkan`, `gl`, `sdl2`, `null`.

```
[ERROR] Couldn't find any video driver named "xvideo"
```

**Решение — `vulkan`** (а не `gl`!): на Zero 3W стоит аппаратный GPU-стек PowerVR
с Vulkan 1.3.277, и RetroArch успешно создаёт vulkan-контекст `vk_x` на GPU
`PowerVR B-Series BXM-4-64 MC1`. Игры (NES/GBC) рендерятся аппаратно, без
llvmpipe-софта.

Проверено: Super Mario Bros (Nestopia) и Shantae (mGBA) запускаются на vulkan,
картинка корректная. `gl` тоже работает, но через llvmpipe (софт) — vulkan быстрее.

В конфигах:
```ini
video_driver = "vulkan"
```

### 3. Путь ядра mGBA

Было (путь из старой раскладки):
```python
CORE = os.path.expanduser("~/.config/retroarch/cores/mgba_libretro.so")
```
Стало (ядра ставятся в системную папку):
```python
CORE = "/usr/lib/aarch64-linux-gnu/libretro/mgba_libretro.so"
```
Затронутый файл: `scripts/select_game_gbc.py`.

### 4. RetroArch теперь ставится из apt

На Debian 11 пришлось подключать backports ради RetroArch 1.14.
На Debian 13 достаточно:
```bash
sudo apt install retroarch libretro-nestopia libretro-mgba libretro-gambatte
```

---

## 🌡 cpu-temperature-panel → индикатор MATE

Репозиторий описывал genmon-плагин для **XFCE**-панели. Активная DE на Debian 13 — **MATE**, где genmon отсутствует.

Решение: тот же скрипт чтения датчика + **AppIndicator в трее**:

```bash
sudo apt install gir1.2-ayatanaappindicator3-0.1
cp cpu-temp/cpu-temp-indicator.py ~/.local/bin/
chmod +x ~/.local/bin/cpu-temp-indicator.py
cp cpu-temp/cpu-temp-indicator.desktop ~/.config/autostart/
```

Скрипт `cpu-temp-indicator.py` показывает `🌡 NN°C` в трее, обновление каждые 5 сек,
чтение из `/sys/class/thermal/thermal_zone0/temp`.

`cpu-temp.sh` (как в оригинале) тоже приложен — работает в любом окружении.

---

## 🎧 bluetooth-hid — приятная новость

Модуль `uhid.ko` из репозитория собран под **6.6.98-sun60iw2** — ядро Debian 13 на
Zero 3W **такое же** (в CONFIG_UHID по-прежнему выключен). Модуль встаёт без
пересборки: vermagic совпал. Инструкция из репозитория работает как есть.

---

## Структура репозитория

```
├── README.md                       ← этот документ
├── retroarch/
│   ├── game_input.py               ← игровой мост (libgpiod v2)
│   ├── mario_buttons.py            ← тестер GPIO-кнопок (libgpiod v2)
│   ├── select_game.py              ← выбор NES (zenity)
│   ├── select_game_gbc.py          ← выбор GBC/GBA (путь ядра исправлен)
│   ├── retrogame.sh                ← лаунчер NES
│   ├── retrogame-gbc.sh            ← лаунчер GBC/GBA
│   ├── scan_roms.py                ← генерация плейлиста
│   ├── config/
│   │   ├── retroarch.cfg           ← NES (video_driver=vulkan)
│   │   └── gbc.cfg                 ← GBC (video_driver=vulkan)
│   └── udev/
│       └── 99-gpio.rules           ← доступ к GPIO для группы input
└── cpu-temp/
    ├── cpu-temp.sh                 ← оригинальный скрипт датчика
    ├── cpu-temp-indicator.py       ← AppIndicator для MATE
    └── cpu-temp-indicator.desktop  ← autostart
```

---

## Быстрая установка (Debian 13)

```bash
# зависимости
sudo apt install -y retroarch libretro-nestopia libretro-mgba libretro-gambatte \
    python3-libgpiod python3-xlib xdotool zenity gpiod \
    gir1.2-ayatanaappindicator3-0.1

# скрипты RetroArch
mkdir -p ~/.openclaw/workspace ~/.config/retroarch ~/roms/nes ~/roms/gbc
cp retroarch/game_input.py retroarch/mario_buttons.py retroarch/select_game.py \
   retroarch/select_game_gbc.py retroarch/retrogame.sh retroarch/retrogame-gbc.sh \
   retroarch/scan_roms.py ~/.openclaw/workspace/
chmod +x ~/.openclaw/workspace/*.sh ~/.openclaw/workspace/*.py

# конфиги RetroArch
cp retroarch/config/retroarch.cfg ~/.config/retroarch/
cp retroarch/config/gbc.cfg ~/.config/retroarch/

# GPIO udev-правило
sudo cp retroarch/udev/99-gpio.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger --subsystem-match=gpio

# ROMs — положить в ~/roms/nes/*.nes и ~/roms/gbc/*.gbc

# индикатор температуры (MATE)
cp cpu-temp/cpu-temp-indicator.py ~/.local/bin/ && chmod +x ~/.local/bin/cpu-temp-indicator.py
cp cpu-temp/cpu-temp-indicator.desktop ~/.config/autostart/
```

Запуск игры: `bash ~/.openclaw/workspace/retrogame.sh` (или иконка на Desktop).
Проверка кнопок: `python3 ~/.openclaw/workspace/mario_buttons.py`.

---

*Оригиналы: [opi-zero3w-retroarch](https://github.com/Haidegger22/opi-zero3w-retroarch) ·
[orangepi-zero3w-cpu-temperature-panel](https://github.com/Haidegger22/orangepi-zero3w-cpu-temperature-panel) ·
[orangepi-zero3w-bluetooth-hid](https://github.com/Haidegger22/orangepi-zero3w-bluetooth-hid) ·
[orangepi-zero3w-chromium-cache-ram](https://github.com/Haidegger22/orangepi-zero3w-chromium-cache-ram) ·
[orangepi-zero3w-chromium-russian](https://github.com/Haidegger22/orangepi-zero3w-chromium-russian)*
