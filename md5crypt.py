# -*- coding: utf-8 -*-
"""Clean Python 3 implementation of FreeBSD/Apache MD5-based crypt()."""

import hashlib

MAGIC = '$1$'
ITOA64 = "./0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


def _to64(v, n):
    ret = []
    while n > 0:
        n -= 1
        ret.append(ITOA64[v & 0x3f])
        v >>= 6
    return ''.join(ret)


def unix_md5_crypt(pw, salt, magic=MAGIC):
    if isinstance(pw, str):
        pw = pw.encode('utf-8')
    if isinstance(salt, str):
        salt = salt.encode('utf-8')
    if isinstance(magic, str):
        magic_b = magic.encode('utf-8')
    else:
        magic_b = magic
        magic = magic.decode('utf-8')

    if salt.startswith(magic_b):
        salt = salt[len(magic_b):]

    salt = salt.split(b'$', 1)[0][:8]
    ctx = bytearray(pw + magic_b + salt)

    final = hashlib.md5(pw + salt + pw).digest()
    for pl in range(len(pw), 0, -16):
        ctx.extend(final[:min(pl, 16)])

    i = len(pw)
    while i:
        if i & 1:
            ctx.append(0)
        else:
            ctx.append(pw[0])
        i >>= 1

    final = hashlib.md5(ctx).digest()

    for i in range(1000):
        ctx1 = bytearray()
        ctx1.extend(pw if (i & 1) else final[:16])
        if i % 3:
            ctx1.extend(salt)
        if i % 7:
            ctx1.extend(pw)
        ctx1.extend(final[:16] if (i & 1) else pw)
        final = hashlib.md5(ctx1).digest()

    passwd = (
        _to64((final[0] << 16) | (final[6] << 8) | final[12], 4) +
        _to64((final[1] << 16) | (final[7] << 8) | final[13], 4) +
        _to64((final[2] << 16) | (final[8] << 8) | final[14], 4) +
        _to64((final[3] << 16) | (final[9] << 8) | final[15], 4) +
        _to64((final[4] << 16) | (final[10] << 8) | final[5], 4) +
        _to64(final[11], 2)
    )
    return magic + salt.decode('utf-8') + '$' + passwd


def apache_md5_crypt(pw, salt):
    return unix_md5_crypt(pw, salt, '$apr1$')


md5crypt = unix_md5_crypt
