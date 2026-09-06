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

#### Команды для терминала (по шагам)

**Шаг 1. Проверить, что аппаратный Vulkan вообще есть** (нужен GPU-стек, см.
[opi-zero3w-gpu-debian13](https://github.com/Haidegger22/opi-zero3w-gpu-debian13)):

```bash
vulkaninfo --summary
# deviceName  = PowerVR B-Series BXM-4-64 MC1  ← аппаратный (НЕ llvmpipe!)
# apiVersion  = 1.3.277
```

**Шаг 2. Установить RetroArch + ядра из apt** (на Debian 13 backports не нужен):

```bash
sudo apt install retroarch libretro-nestopia libretro-mgba libretro-gambatte
```

**Шаг 3. Включить vulkan-драйвер в конфиге** — готовый конфиг из этого репозитория:

```bash
mkdir -p ~/.config/retroarch
cp retroarch/config/retroarch.cfg ~/.config/retroarch/retroarch.cfg   # NES
cp retroarch/config/gbc.cfg ~/.config/retroarch/gbc.cfg               # GBC/GBA
```

Или одной строкой вручную (если конфиг уже есть):

```bash
# заменить/добавить строку в ~/.config/retroarch/retroarch.cfg:
sed -i 's/^video_driver.*/video_driver = "vulkan"/' ~/.config/retroarch/retroarch.cfg \
  || echo 'video_driver = "vulkan"' >> ~/.config/retroarch/retroarch.cfg
```

**Шаг 4. Запустить игру и убедиться, что рендер аппаратный:**

```bash
# через лаунчер (NES):
retroarch -L /usr/lib/aarch64-linux-gnu/libretro/nestopia_libretro.so ~/roms/nes/ИГРА.nes

# в логе при старте ищи строку про vulkan (а НЕ про llvmpipe):
retroarch --verbose 2>&1 | grep -iE "vulkan|llvmpipe|PowerVR"
```

Признак успеха: в `--verbose`-логе есть Vulkan/`PowerVR`, и нет падения в llvmpipe.

В конфигах (готовые лежат в `retroarch/config/`):
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

### 5. I2C-доступ — БЕЗ ЭТОГО управление не работает!

На Debian 13 пользователь не имеет доступа к `/dev/i2c-0` (устройство `root:i2c 660`, группы `i2c` нет) → игровой мост `game_input.py` падает при старте:
```
PermissionError: [Errno 13] Permission denied: '/dev/i2c-0'
```
Симптом: игра запускается, картинка есть, но джойстик/GPIO-кнопки/CardKB не работают, окно не закрыть (m5hub уже остановлен лаунчером, а мост мёртв).

Решение — в udev-правиле (`udev/99-gpio.rules`) дать доступ к i2c-dev группе `input`:
```bash
sudo cp retroarch/udev/99-gpio.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=i2c-dev --subsystem-match=gpio
```
Проверка: `ls -la /dev/i2c-0` → должно быть `root input`.

### 6. Окно выбора игр — высота под экран 1024×600

zenity-окно выбора ROM было `--height=320` (видны ~3 игры, остальное скроллом).
Увеличено до `--height=530 --width=560` — видно ~8 игр без прокрутки.
Затронутые файлы: `select_game.py`, `select_game_gbc.py`.

### 7. OSD-уведомления RetroArch

После установки русской локали (`ru_RU.UTF-8`) RetroArch пишет OSD-уведомления
по-русски, а **встроенный шрифт не содержит кириллицы** → поверх игры появляется
`?????`. Два решения (оба в конфигах `config/*.cfg`):

1. Поставить системный шрифт с кириллицей:
```ini
video_font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
```
2. Либо вообще отключить всплывающие уведомления:
```ini
video_font_enable = "false"
```

---

## 🌡 cpu-temperature-panel → плавающий виджет (float) на рабочем столе

Репозиторий описывал genmon-плагин для **XFCE**-панели. Активная DE на Debian 13 — **MATE**.

Важный нюанс: python-gi **AyatanaAppIndicator3 не регистрируется** на Zero 3W/Debian 13
(индикатор молчит в SNI-watcher, иконка в трее не появляется), поэтому AppIndicator-путь
отбрасываем. Рабочее решение — **плавающий полупрозрачный виджет-градусник** прямо на
рабочем столе: рисуется через Cairo (GTK3), висит поверх всех окон, перетаскивается
мышью (левая/правая кнопка), закрывается средним кликом, обновляется каждые 5 сек.

```bash
# зависимость — только GTK3 (есть в MATE по умолчанию)
cp cpu-temp/cpu-temp-float.py ~/.local/bin/
chmod +x ~/.local/bin/cpu-temp-float.py
cp cpu-temp/cpu-temp-float.desktop ~/.config/autostart/
```

Запуск вручную:

```bash
DISPLAY=:0 ~/.local/bin/cpu-temp-float.py
```

Виджет `cpu-temp-float.py` показывает градусник + `NN°` (например `35°`) в правом
нижнем углу (стартовая позиция), чтение из `/sys/class/thermal/thermal_zone0/temp`.
Цвет индикатора: зелёный <50°, жёлтый <70°, красный >=70°.

Управление:
- **левая/правая кнопка мыши** — перетаскивание
- **средний клик** — закрыть виджет
- **позиция запоминается** на время сессии (автозапуск ставит в правый нижний угол;
  смещение настраивается в коде: `self.move(mw - W - 16, mh - H - 20)`)

Полный текст скрипта `cpu-temp/cpu-temp-float.py`:

```python
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
```

---

## 🎧 bluetooth-hid — приятная новость

Модуль `uhid.ko` из репозитория собран под **6.6.98-sun60iw2** — ядро Debian 13 на
Zero 3W **такое же** (в CONFIG_UHID по-прежнему выключен). Модуль встаёт без
пересборки: vermagic совпал. Инструкция из репозитория работает как есть.

---

## 🔌 FlClashX (прокси/VPN) — фиксы под Debian 13 (06.09.2026)

Отдельный репозиторий с полной инструкцией: [opi-zero3w-flclashx-debian13](https://github.com/Haidegger22/opi-zero3w-flclashx-debian13).
Здесь — краткая выжимка двух фиксов, найденных на практике:

### 1. Чёрное окно GUI при запуске из меню/панели

Env-обвязка (`LD_LIBRARY_PATH=/usr/lib/aarch64-linux-gnu LIBGL_ALWAYS_SOFTWARE=1`)
нужна НЕ только в autostart, но и в системном ярлыке `/usr/share/applications/FlClashX.desktop`
(в deb-пакете там `Exec=FlClashX %U` без env → PVR-враппер libEGL → чёрное окно).

```bash
sudo sed -i 's|^Exec=.*|Exec=env LD_LIBRARY_PATH=/usr/lib/aarch64-linux-gnu LIBGL_ALWAYS_SOFTWARE=1 /usr/bin/FlClashX %U|' /usr/share/applications/FlClashX.desktop
```

### 2. Chromium ходит мимо прокси (российский IP) — расширение SwitchyOmega

Прокси-ядро работает (`curl -x 127.0.0.1:7890` даёт зарубежный IP), но браузер
показывает российский IP и не открывает YouTube (`ERR_FAILED`). Причина — расширение
**Proxy SwitchyOmega** в Chromium (id `omghfjlpggmjjaagoclmmobgdodcjboh`): оно имеет
право `proxy` и перекрывает и системный прокси, и флаг `--proxy-server`.

Решение: удалить расширение из `~/.config/chromium/Default/Extensions/` и вычистить
запись из `Preferences`. После этого браузер ходит через прокси FlClashX
(проверка: `api.ipify.org` в браузере = зарубежный IP).

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
│   │   ├── retroarch.cfg           ← NES (video_driver=vulkan, OSD выкл)
│   │   └── gbc.cfg                 ← GBC (video_driver=vulkan, OSD выкл)
│   └── udev/
│       └── 99-gpio.rules           ← GPIO + I2C доступ для группы input
└── cpu-temp/
    ├── cpu-temp-float.py            ← плавающий виджет-градусник (Cairo/GTK3)
    └── cpu-temp-float.desktop       ← autostart
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

# плавающий виджет температуры (MATE, float)
cp cpu-temp/cpu-temp-float.py ~/.local/bin/ && chmod +x ~/.local/bin/cpu-temp-float.py
cp cpu-temp/cpu-temp-float.desktop ~/.config/autostart/
```

Запуск игры: `bash ~/.openclaw/workspace/retrogame.sh` (или иконка на Desktop).
Проверка кнопок: `python3 ~/.openclaw/workspace/mario_buttons.py`.

---

*Оригиналы: [opi-zero3w-retroarch](https://github.com/Haidegger22/opi-zero3w-retroarch) ·
[orangepi-zero3w-cpu-temperature-panel](https://github.com/Haidegger22/orangepi-zero3w-cpu-temperature-panel) ·
[orangepi-zero3w-bluetooth-hid](https://github.com/Haidegger22/orangepi-zero3w-bluetooth-hid) ·
[orangepi-zero3w-chromium-cache-ram](https://github.com/Haidegger22/orangepi-zero3w-chromium-cache-ram) ·
[orangepi-zero3w-chromium-russian](https://github.com/Haidegger22/orangepi-zero3w-chromium-russian)*
