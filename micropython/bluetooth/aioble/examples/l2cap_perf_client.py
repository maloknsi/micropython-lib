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
import binascii
import hashlib

import time

_L2CAP_PSN = const(22)

# wb55 to wb55: 300/240

_L2CAP_MTU = const(300)
_L2CAP_CHUNK_SIZE = const(240)

_TOTAL_BYTES = const(10*1024)

_CONNECTION_INTERVAL_MS = const(8)


async def find_perf_server():
    # Scan for 5 seconds, in active mode, with very low interval/window (to
    # maximise detection rate).
    async with aioble.scan(5000, interval_us=30000, window_us=30000, active=True) as scanner:
        async for result in scanner:
            # Match by name only.
            if result.name() == "mpy-l2cap-perf":
                return result.device
    return None


async def main():
    device = await find_perf_server()
    if not device:
        print("Perf server not found")
        return

    try:
        connection = await device.connect(conn_interval_ms=_CONNECTION_INTERVAL_MS)
    except asyncio.TimeoutError:
        print("Timeout during connection")
        return

    await asyncio.sleep_ms(1000)

    try:
        channel = await connection.l2cap_connect(_L2CAP_PSN, _L2CAP_MTU)
    except asyncio.TimeoutError:
        print("Timeout during connection")
        return

    buf = bytearray(_TOTAL_BYTES)
    mv = memoryview(buf)

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
    print(f"Received hash {rx_hash} at {(_TOTAL_BYTES-first_chunk) * 1000 // time.ticks_diff(time_end, time_start)} B/s")

    await channel.disconnect()
    await connection.disconnect()


asyncio.run(main())
