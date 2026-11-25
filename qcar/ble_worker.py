import asyncio
import queue
import threading

from bleak import BleakClient, BleakScanner

from . import protocol

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