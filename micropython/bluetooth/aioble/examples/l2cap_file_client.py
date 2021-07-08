# MIT license; Copyright (c) 2021 Jim Mussared

# This is a WIP client for l2cap_file_server.py. See that file for more
# information.

import sys

sys.path.append("")

from micropython import const

import uasyncio as asyncio
import aioble
import bluetooth

import random
import struct
import time

_FILE_SERVICE_UUID = bluetooth.UUID("0492fcec-7194-11eb-9439-0242ac130002")
_CONTROL_CHARACTERISTIC_UUID = bluetooth.UUID("0492fcec-7194-11eb-9439-0242ac130003")


_COMMAND_SEND = const(0)
_COMMAND_RECV = const(1)  # Not yet implemented.
_COMMAND_LIST = const(2)
_COMMAND_SIZE = const(3)
_COMMAND_DONE = const(4)

_STATUS_OK = const(0)
_STATUS_NOT_IMPLEMENTED = const(1)
_STATUS_NOT_FOUND = const(2)

_L2CAP_PSN = const(22)
_L2CAP_MTU = const(512)


class FileError(Exception):
    pass


class FileClient:
    def __init__(self, device):
        self._device = device
        self._connection = None
        self._seq = 1

    async def connect(self):
        try:
            print("Connecting to", self._device)
            self._connection = await self._device.connect()
        except asyncio.TimeoutError:
            print("Timeout during connection")
            return

        try:
            print("Discovering...")
            file_service = await self._connection.service(_FILE_SERVICE_UUID)
            self._control_characteristic = await file_service.characteristic(
                _CONTROL_CHARACTERISTIC_UUID
            )
        except asyncio.TimeoutError:
            print("Timeout discovering services/characteristics")
            return

        print("Connecting channel")
        self._channel = await self._connection.l2cap_connect(_L2CAP_PSN, _L2CAP_MTU)

    async def _command(self, cmd, data):
        send_seq = self._seq
        await self._control_characteristic.write(struct.pack("<BB", cmd, send_seq) + data)
        self._seq += 1
        return send_seq

    async def size(self, path):
        print("Getting size")
        send_seq = await self._command(_COMMAND_SIZE, path.encode())

        data = await self._control_characteristic.notified()
        if len(data) != 3 and len(data) != 7:
            raise FileError("Invalid response")

        cmd, seq, status = struct.unpack("<BBB", data[0:3])
        if seq != send_seq:
            raise FileError("Wrong reply")

        if status == _STATUS_OK:
            size = struct.unpack('<I', data[3:])[0]
            print("result:", seq, status, size)
            return size

        if status == _STATUS_NOT_FOUND:
            raise FileError("Not found")
        else:
            raise FileError("Unknown")


    async def download(self, path, dest):
        size = await self.size(path)

        send_seq = await self._command(_COMMAND_SEND, path.encode())

        with open(dest, "wb") as f:
            total = 0
            buf = bytearray(self._channel.our_mtu)
            mv = memoryview(buf)
            while total < size:
                n = await self._channel.recvinto(buf)
                f.write(mv[:n])
                total += n

    async def list(self, path):
        send_seq = await self._command(_COMMAND_LIST, path.encode())
        data = bytearray()
        buf = bytearray(self._channel.our_mtu)
        mv = memoryview(buf)
        while True:
            n = await self._channel.recvinto(buf)
            data += mv[:n]
            if data[len(data) - 1] == ord("\n") and data[len(data) - 2] == ord("\n"):
                break
        results = []
        for entry in data.decode().split("\n"):
            entry = entry.split(':')
            if len(entry) != 2:
                continue
            results.append((int(entry[0]), entry[1]))
        return results

    async def disconnect(self):
        if self._connection:
            await self._connection.disconnect()


async def main():
    async with aioble.scan(5000, 30000, 30000, active=True) as scanner:
        async for result in scanner:
            if result.name() == "mpy-file" and _FILE_SERVICE_UUID in result.services():
                device = result.device
                break
        else:
            print("File server not found")
            return

    client = FileClient(device)

    await client.connect()
    print(await client.size("/tmp/demo/file.txt"))

    try:
        print(await client.size("/tmp/demo/notfound.bin"))
    except FileError:
        print("Not found")

    s = await client.size("/tmp/demo/big.dat")
    t = time.ticks_ms()
    await client.download("/tmp/demo/big.dat", "/tmp/download.txt")
    dt = time.ticks_diff(time.ticks_ms(), t)
    print("Download took {}ms ({} b/s).".format(dt, int(s*1000/dt)))

    for f in await client.list("/tmp/demo"):
        print(f)

    await client.disconnect()


asyncio.run(main())
