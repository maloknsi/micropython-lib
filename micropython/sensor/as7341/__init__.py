import machine


_AS7341_I2CADDR_DEFAULT = const(0x39)
_AS7341_DEVICE_ID = const(0b001001)

_AS7341_CONFIG = const(0x70)
_AS7341_LED = const(0x74)

_AS7341_ENABLE = const(0x80)
_AS7341_WHOAMI = const(0x92)

_AS7341_CFG0 = const(0xA9)

class AS7341:
    def __init__(self, i2c):
        if _AS7341_I2CADDR_DEFAULT not in i2c.scan():
            raise ValueError("Device not found")

        self.i2c = i2c

        self.buf = bytearray(1)
        if self._read(_AS7341_WHOAMI) >> 2 != _AS7341_DEVICE_ID:
            raise ValueError("Invalid device")

        # Power on
        self._high()
        self._set(_AS7341_ENABLE, 0)

        # Enable LED control
        self._low()
        self._set(_AS7341_CONFIG, 3)

    def _read(self, addr):
        self.i2c.readfrom_mem_into(_AS7341_I2CADDR_DEFAULT, addr, self.buf)
        return self.buf[0]

    def _write(self, addr, v):
        self.buf[0] = v
        self.i2c.writeto_mem(_AS7341_I2CADDR_DEFAULT, addr, self.buf)

    def _set(self, addr, bit):
        v = self._read(addr)
        v |= 1 << bit
        self._write(addr, v)

    def _clear(self, addr, bit):
        v = self._read(addr)
        v &= ~(1 << bit)
        self._write(addr, v)

    def _low(self):
        self._set(_AS7341_CFG0, 4)

    def _high(self):
        self._clear(_AS7341_CFG0, 4)

    def led(self, v=None):
        if v is None:
            v = self._read(_AS7341_LED)
            if v & 0b10000000:
                return (v & 0b1111111) * 2 + 4
            else:
                return 0
        else:
            if v:
                # LED on
                self._low()
                self._write(_AS7341_LED, 0b10000000 | min(0b1111111, max(0, v - 4) // 2))
            else:
                self._write(_AS7341_LED, 0)

i2c = machine.I2C('X', freq=400000)
d = AS7341(i2c)
d.led(0)
