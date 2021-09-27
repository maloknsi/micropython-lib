# MIT license; Copyright (c) 2021 Jim Mussared

# This is a BLE file server, based very loosely on the Object Transfer Service
# specification. It demonstrated transfering data over an L2CAP channel, as
# well as using notifications and GATT writes on a characteristic.

# The server supports downloading and uploading files, as well as querying
# directory listings and file sizes.

# In order to access the file server, a client must connect, then establish an
# L2CAP channel. To being an operation, a command is written to the control
# characteristic, including a command number, sequence number, and filesystem
# path. The response will be either via a notification on the control
# characteristic (e.g. file size), or via the L2CAP channel (file contents or
# directory listing).

import sys

sys.path.append("")

from micropython import const

import uasyncio as asyncio
import aioble
import bluetooth

import binascii
import hashlib
import random

import time

# How frequently to send advertising beacons.
_ADV_INTERVAL_MS = const(250_000)

_L2CAP_PSN = const(22)
_L2CAP_MTU = const(300)

_L2CAP_CHUNK_SIZE = const(240)

_TOTAL_BYTES = const(10*1024)


# Run both tasks.
async def main():
    while True:
        print("Waiting for connection")
        connection = await aioble.advertise(
            _ADV_INTERVAL_MS,
            name="mpy-l2cap-perf",
        )
        print("Connection from", connection.device)

        channel = await connection.l2cap_accept(_L2CAP_PSN, _L2CAP_MTU)
        print("Channel accepted")

        buf = bytearray(_TOTAL_BYTES)
        mv = memoryview(buf)

        sha256 = hashlib.sha256()
        n = 0
        first_chunk = 0
        while n < _TOTAL_BYTES:
            chunk = await channel.recvinto(buf)
            if n == 0:
                time_start = time.ticks_ms()
                first_chunk = chunk
            sha256.update(mv[0:chunk])
            # print("Received", chunk)
            n += chunk
        time_end = time.ticks_ms()
        rx_hash = binascii.hexlify(sha256.digest()[0:8]).decode()
        print(f"Received hash {rx_hash} at {(_TOTAL_BYTES - first_chunk) * 1000 // time.ticks_diff(time_end, time_start)} B/s")

        for i in range(_TOTAL_BYTES):
            buf[i] = random.randint(0, 255)
        sha256 = hashlib.sha256()
        sha256.update(buf)
        tx_hash = binascii.hexlify(sha256.digest()[0:8]).decode()
        print(f"Sending {_TOTAL_BYTES} bytes with hash {tx_hash}")
        time_start = time.ticks_ms()
        await channel.send(buf, chunk_size=_L2CAP_CHUNK_SIZE)
        await channel.flush()
        time_end = time.ticks_ms()
        print(f"Sent at {_TOTAL_BYTES * 1000 // time.ticks_diff(time_end, time_start)} B/s")

        await connection.disconnected()
        print("Disconnected")


asyncio.run(main())
