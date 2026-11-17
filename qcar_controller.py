"""
QCar Controller
Windows-friendly BLE controller for compatible BrandBase / Shell "QCAR-..." batteries.
Tested with one micro-USB and one USB-C battery revision.

Controls:
  W / Up       Forward
  S / Down     Reverse
  A / Left     Steer left
  D / Right    Steer right
  Shift        Turbo (100%)
  Space / Esc  Emergency stop
  L            Toggle lights
"""

import asyncio
import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox

try:
    from bleak import BleakClient, BleakScanner
    import qcar.protocol as protocol
except ImportError as exc:
    raise SystemExit(
        "Missing dependency. Run setup.bat first.\n"
        "Required: bleak, pycryptodome"
    ) from exc


__version__ = "0.1.0"
APP_NAME = "QCar Controller"


SEND_INTERVAL = 0.05  # 50 ms; responsive without hammering Windows BLE


class BleWorker:
    def __init__(self, ui_queue: queue.Queue):
        self.ui_queue = ui_queue
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._thread_main, daemon=True)

        self.devices = {}
        self.client = None
        self.control_task = None
        self.connected = False

        self.state_lock = threading.Lock()
        self.forward = False
        self.reverse = False
        self.left = False
        self.right = False
        self.turbo = False
        self.lights = False
        self.normal_speed = 0x50

        self.thread.start()

    def _thread_main(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def submit(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    def post(self, kind, value):
        self.ui_queue.put((kind, value))

    async def scan(self):
        self.post("status", "Scanning for QCAR devices...")
        try:
            found = await BleakScanner.discover(timeout=6.0)
            qcars = []
            self.devices = {}

            for dev in found:
                name = (dev.name or "").strip()
                if name.upper().startswith("QCAR-"):
                    label = f"{name}   [{dev.address}]"
                    self.devices[label] = dev
                    qcars.append(label)

            qcars.sort()
            self.post("devices", qcars)

            if qcars:
                self.post("status", f"Found {len(qcars)} QCAR device(s).")
            else:
                self.post(
                    "status",
                    "No QCAR device found. Turn the battery on and disconnect it from the phone."
                )
        except Exception as exc:
            self.post("error", f"Bluetooth scan failed:\n{exc}")

    async def connect(self, label):
        if not label or label not in self.devices:
            self.post("error", "Select a QCAR device first.")
            return

        await self.disconnect(silent=True)
        device = self.devices[label]
        self.post("status", f"Connecting to {device.name or device.address}...")

        try:
            self.client = BleakClient(device, disconnected_callback=self._on_disconnected)
            await self.client.connect(timeout=12.0)
            self.connected = bool(self.client.is_connected)

            if not self.connected:
                raise RuntimeError("Windows reported that the BLE connection was not established.")

            try:
                await self.client.start_notify(protocol.NOTIFY_UUID, self._battery_notification)
            except Exception as exc:
                # Driving can still work even if notifications are unavailable.
                self.post("status", f"Connected. Battery readout unavailable: {exc}")
            else:
                self.post("status", f"Connected to {device.name or device.address}")

            self.post("connected", True)
            self.control_task = asyncio.create_task(self._control_loop())

        except Exception as exc:
            self.connected = False
            self.client = None
            self.post("connected", False)
            self.post(
                "error",
                "Connection failed.\n\n"
                f"{exc}\n\n"
                "Tip: close Shell Racing on your phone and make sure the battery is switched on."
            )

    async def disconnect(self, silent=False):
        self.connected = False

        if self.control_task:
            self.control_task.cancel()
            try:
                await self.control_task
            except (asyncio.CancelledError, Exception):
                pass
            self.control_task = None

        if self.client:
            try:
                if self.client.is_connected:
                    try:
                        await self._write_current(force_stop=True)
                        await asyncio.sleep(0.05)
                    except Exception:
                        pass

                    try:
                        await self.client.stop_notify(protocol.NOTIFY_UUID)
                    except Exception:
                        pass

                    await self.client.disconnect()
            except Exception:
                pass

        self.client = None
        self.post("connected", False)
        if not silent:
            self.post("status", "Disconnected.")

    def _on_disconnected(self, _client):
        self.connected = False
        self.post("connected", False)
        self.post("status", "Bluetooth disconnected.")

    def _battery_notification(self, _sender, data: bytearray):
        try:
            battery = protocol.decode_battery_notification(bytes(data))
            if battery is not None:
                self.post("battery", battery)
        except Exception:
            pass

    def set_key_state(self, key, pressed):
        with self.state_lock:
            if key == "forward":
                self.forward = pressed
            elif key == "reverse":
                self.reverse = pressed
            elif key == "left":
                self.left = pressed
            elif key == "right":
                self.right = pressed
            elif key == "turbo":
                self.turbo = pressed

    def emergency_stop(self):
        with self.state_lock:
            self.forward = False
            self.reverse = False
            self.left = False
            self.right = False
            self.turbo = False

    def set_lights(self, value):
        with self.state_lock:
            self.lights = bool(value)

    def set_speed(self, value):
        value = max(0x16, min(0x64, int(value)))
        with self.state_lock:
            self.normal_speed = value

    def _make_packet(self, force_stop=False):
        with self.state_lock:
            forward = False if force_stop else self.forward
            reverse = False if force_stop else self.reverse
            left = False if force_stop else self.left
            right = False if force_stop else self.right
            turbo = False if force_stop else self.turbo
            lights = self.lights
            normal_speed = self.normal_speed

        return protocol.encode_control_packet(
            forward=forward,
            reverse=reverse,
            left=left,
            right=right,
            turbo=turbo,
            lights=lights,
            normal_speed=normal_speed,
        )

    async def _write_current(self, force_stop=False):
        if not self.client or not self.client.is_connected:
            return
        packet = self._make_packet(force_stop=force_stop)
        # Let Bleak choose write-with-response vs write-without-response
        # from the characteristic properties; this is safer across Windows BLE stacks.
        await self.client.write_gatt_char(protocol.WRITE_UUID, packet)

    async def _control_loop(self):
        try:
            while self.connected and self.client and self.client.is_connected:
                await self._write_current()
                await asyncio.sleep(SEND_INTERVAL)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.connected = False
            self.post("connected", False)
            self.post("error", f"Bluetooth write failed:\n{exc}")


class App:
    KEYMAP = {
        "w": "forward",
        "Up": "forward",
        "s": "reverse",
        "Down": "reverse",
        "a": "left",
        "Left": "left",
        "d": "right",
        "Right": "right",
    }

    def __init__(self, root):
        self.root = root
        self.root.title(f"{APP_NAME} v{__version__}")
        self.root.geometry("620x500")
        self.root.minsize(560, 450)

        self.ui_queue = queue.Queue()
        self.worker = BleWorker(self.ui_queue)

        self.pressed = set()
        self.connected_var = tk.StringVar(value="Disconnected")
        self.status_var = tk.StringVar(value="Turn the battery on, then press Scan.")
        self.battery_var = tk.StringVar(value="—")
        self.lights_var = tk.BooleanVar(value=False)
        self.speed_var = tk.IntVar(value=80)

        self._build_ui()
        self._bind_keys()

        self.root.after(80, self._poll_worker)
        self.root.protocol("WM_DELETE_WINDOW", self._close)

    def _build_ui(self):
        pad = {"padx": 12, "pady": 8}

        title = ttk.Label(
            self.root,
            text=APP_NAME,
            font=("Segoe UI", 18, "bold")
        )
        title.pack(pady=(16, 4))

        ttk.Label(
            self.root,
            text="Bluetooth LE controller for compatible Shell / BrandBase QCAR batteries",
            font=("Segoe UI", 10)
        ).pack(pady=(0, 12))

        top = ttk.Frame(self.root)
        top.pack(fill="x", **pad)

        self.device_box = ttk.Combobox(top, state="readonly")
        self.device_box.pack(side="left", fill="x", expand=True)

        self.scan_btn = ttk.Button(top, text="Scan", command=self._scan)
        self.scan_btn.pack(side="left", padx=(8, 0))

        self.connect_btn = ttk.Button(top, text="Connect", command=self._connect)
        self.connect_btn.pack(side="left", padx=(8, 0))

        info = ttk.Frame(self.root)
        info.pack(fill="x", **pad)
        ttk.Label(info, text="Connection:").grid(row=0, column=0, sticky="w")
        ttk.Label(info, textvariable=self.connected_var).grid(row=0, column=1, sticky="w", padx=(8, 28))
        ttk.Label(info, text="Battery:").grid(row=0, column=2, sticky="w")
        ttk.Label(info, textvariable=self.battery_var).grid(row=0, column=3, sticky="w", padx=(8, 0))

        controls = ttk.LabelFrame(self.root, text="Controls")
        controls.pack(fill="x", **pad)

        grid = ttk.Frame(controls)
        grid.pack(pady=10)

        self.btn_up = ttk.Button(grid, text="W / ↑\nForward", width=14)
        self.btn_left = ttk.Button(grid, text="A / ←\nLeft", width=14)
        self.btn_stop = ttk.Button(grid, text="SPACE\nSTOP", width=14, command=self._stop)
        self.btn_right = ttk.Button(grid, text="D / →\nRight", width=14)
        self.btn_down = ttk.Button(grid, text="S / ↓\nReverse", width=14)

        self.btn_up.grid(row=0, column=1, padx=4, pady=4)
        self.btn_left.grid(row=1, column=0, padx=4, pady=4)
        self.btn_stop.grid(row=1, column=1, padx=4, pady=4)
        self.btn_right.grid(row=1, column=2, padx=4, pady=4)
        self.btn_down.grid(row=2, column=1, padx=4, pady=4)

        self._bind_hold_button(self.btn_up, "forward")
        self._bind_hold_button(self.btn_down, "reverse")
        self._bind_hold_button(self.btn_left, "left")
        self._bind_hold_button(self.btn_right, "right")

        options = ttk.Frame(self.root)
        options.pack(fill="x", **pad)

        ttk.Label(options, text="Normal speed:").grid(row=0, column=0, sticky="w")
        self.speed_scale = ttk.Scale(
            options,
            from_=22,
            to=100,
            orient="horizontal",
            command=self._speed_changed
        )
        self.speed_scale.set(80)
        self.speed_scale.grid(row=0, column=1, sticky="ew", padx=10)
        self.speed_label = ttk.Label(options, text="80%")
        self.speed_label.grid(row=0, column=2, sticky="e")
        options.columnconfigure(1, weight=1)

        lights = ttk.Checkbutton(
            options,
            text="Lights (L)",
            variable=self.lights_var,
            command=self._lights_changed
        )
        lights.grid(row=1, column=0, sticky="w", pady=(10, 0))

        ttk.Label(
            options,
            text="Hold SHIFT = Turbo 100%",
            font=("Segoe UI", 10, "bold")
        ).grid(row=1, column=1, sticky="w", pady=(10, 0))

        status = ttk.LabelFrame(self.root, text="Status")
        status.pack(fill="both", expand=True, **pad)
        ttk.Label(
            status,
            textvariable=self.status_var,
            wraplength=560,
            justify="left"
        ).pack(anchor="w", padx=10, pady=10)

        ttk.Label(
            self.root,
            text="Tip: click this window once before driving so it receives the keyboard keys.",
            font=("Segoe UI", 9)
        ).pack(pady=(0, 12))

    def _bind_hold_button(self, button, direction):
        button.bind("<ButtonPress-1>", lambda _e, d=direction: self.worker.set_key_state(d, True))
        button.bind("<ButtonRelease-1>", lambda _e, d=direction: self.worker.set_key_state(d, False))
        button.bind("<Leave>", lambda _e, d=direction: self.worker.set_key_state(d, False))

    def _bind_keys(self):
        self.root.bind_all("<KeyPress>", self._key_down)
        self.root.bind_all("<KeyRelease>", self._key_up)

    def _key_down(self, event):
        key_id = (event.keysym, event.keycode)
        if key_id in self.pressed:
            return
        self.pressed.add(key_id)

        keysym = event.keysym
        lower = keysym.lower()

        if keysym in self.KEYMAP:
            self.worker.set_key_state(self.KEYMAP[keysym], True)
        elif lower in self.KEYMAP:
            self.worker.set_key_state(self.KEYMAP[lower], True)
        elif keysym in ("Shift_L", "Shift_R"):
            self.worker.set_key_state("turbo", True)
            self.status_var.set("TURBO: 100%")
        elif keysym in ("space", "Escape"):
            self._stop()
        elif lower == "l":
            self.lights_var.set(not self.lights_var.get())
            self._lights_changed()

    def _key_up(self, event):
        self.pressed.discard((event.keysym, event.keycode))

        keysym = event.keysym
        lower = keysym.lower()

        if keysym in self.KEYMAP:
            self.worker.set_key_state(self.KEYMAP[keysym], False)
        elif lower in self.KEYMAP:
            self.worker.set_key_state(self.KEYMAP[lower], False)
        elif keysym in ("Shift_L", "Shift_R"):
            self.worker.set_key_state("turbo", False)
            if self.connected_var.get() == "Connected":
                self.status_var.set("Connected — ready.")

    def _scan(self):
        self.scan_btn.configure(state="disabled")
        self.worker.submit(self.worker.scan())

    def _connect(self):
        if self.connected_var.get() == "Connected":
            self.worker.submit(self.worker.disconnect())
            return

        label = self.device_box.get()
        if not label:
            messagebox.showinfo(APP_NAME, "Press Scan and select the QCAR device first.")
            return
        self.worker.submit(self.worker.connect(label))

    def _stop(self):
        self.worker.emergency_stop()
        self.status_var.set("STOP — movement commands cleared.")

    def _lights_changed(self):
        self.worker.set_lights(self.lights_var.get())

    def _speed_changed(self, value):
        speed = int(float(value))
        self.speed_var.set(speed)
        self.speed_label.configure(text=f"{speed}%")
        self.worker.set_speed(speed)

    def _poll_worker(self):
        try:
            while True:
                kind, value = self.ui_queue.get_nowait()

                if kind == "status":
                    self.status_var.set(str(value))
                elif kind == "devices":
                    self.scan_btn.configure(state="normal")
                    self.device_box["values"] = value
                    if value:
                        self.device_box.current(0)
                elif kind == "connected":
                    if value:
                        self.connected_var.set("Connected")
                        self.connect_btn.configure(text="Disconnect")
                    else:
                        self.connected_var.set("Disconnected")
                        self.connect_btn.configure(text="Connect")
                        self.battery_var.set("—")
                elif kind == "battery":
                    self.battery_var.set(f"{value}%")
                elif kind == "error":
                    self.scan_btn.configure(state="normal")
                    self.status_var.set(str(value).splitlines()[0])
                    messagebox.showerror(APP_NAME, str(value))

        except queue.Empty:
            pass

        self.root.after(80, self._poll_worker)

    def _close(self):
        self.worker.emergency_stop()
        try:
            fut = self.worker.submit(self.worker.disconnect(silent=True))
            fut.result(timeout=2.0)
        except Exception:
            pass
        self.root.destroy()


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
