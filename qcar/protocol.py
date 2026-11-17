from Crypto.Cipher import AES

SERVICE_UUID = "0000fff0-0000-1000-8000-00805f9b34fb"
WRITE_UUID = "d44bc439-abfd-45a2-b575-925416129600"
NOTIFY_UUID = "d44bc439-abfd-45a2-b575-925416129601"

AES_KEY = bytes.fromhex("34522a5b7a6e492c08090a9d8d2a23f8")

# Packet layout tested with our micro-USB and USB-C battery revisions:
# [0] unknown/0
# [1:4] b"CTL"
# [4] forward
# [5] reverse
# [6] left
# [7] right
# [8] lights: 0=on, 1=off
# [9] speed/power: 0x50 normal, 0x64 turbo
# [10:16] zero padding


def encode_control_packet(
    *,
    forward: bool,
    reverse: bool,
    left: bool,
    right: bool,
    turbo: bool,
    lights: bool,
    normal_speed: int,
) -> bytes:
    speed = 0x64 if turbo else normal_speed

    cmd = bytearray(16)
    cmd[1:4] = b"CTL"
    cmd[4] = 1 if forward else 0
    cmd[5] = 1 if reverse else 0
    cmd[6] = 1 if left else 0
    cmd[7] = 1 if right else 0
    cmd[8] = 0 if lights else 1
    cmd[9] = speed
    return AES.new(AES_KEY, AES.MODE_ECB).encrypt(bytes(cmd))

def decode_battery_notification(data: bytes) -> int | None:
    if len(data) != 16:
        return None

    plain = AES.new(AES_KEY, AES.MODE_ECB).decrypt(data)

    if plain[1:4] != b"VBT":
        return None

    return plain[4]
