#!/usr/bin/env python

from os import environ
from socket import htons, socket, error, AF_INET, SOCK_DGRAM
from time import sleep

def encode(n):
    high, l = True, 0
    chunk = []

    for i in range(12):
        if n & (1 << i):
            if not high:
                chunk.append(l)
                high = True
                l = 0

        else:
            if high:
                chunk.append(l)
                high = False
                l = 0

        l += 1

    return chunk

def bars(chunk):
    result = ''

    for i, l in enumerate(chunk):
        result += (i & 1 and '-' or '#') * l

    return result

addr = environ.get('HOST', '127.0.0.1'), (8765)
sock = socket(AF_INET, SOCK_DGRAM)
repeat = int(environ.get('REPEAT'))

for key in range(160):
    if repeat:
        key = repeat

    key  = key * 7 + 64
    code = encode(key)

    data = [255, 255, 64, 128]

    for i, l in enumerate(code):
        l *= 2000

        lo, hi = (l & 255), (l >> 8) & 255

        if i % 2:
            hi |= 128

        data.extend((lo, hi,))

    data.extend((64, 128, 255, 255,))

    print key, bars(code), data

    data = ''.join(map(chr, data))
    sock.sendto(data, 0, addr)

    sleep(0.5)
