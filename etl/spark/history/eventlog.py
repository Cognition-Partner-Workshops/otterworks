"""Read and write Spark zstd event logs using Ubuntu's libzstd."""
import ctypes
from ctypes.util import find_library
from functools import lru_cache
import json


class InputBuffer(ctypes.Structure):
    _fields_ = [("src", ctypes.c_void_p), ("size", ctypes.c_size_t), ("pos", ctypes.c_size_t)]


class OutputBuffer(ctypes.Structure):
    _fields_ = [("dst", ctypes.c_void_p), ("size", ctypes.c_size_t), ("pos", ctypes.c_size_t)]


@lru_cache(maxsize=1)
def library():
    name = find_library("zstd")
    if not name:
        raise RuntimeError("libzstd.so.1 is required (Ubuntu package libzstd1)")
    lib = ctypes.CDLL(name)
    signatures = {
        "ZSTD_createDStream": (ctypes.c_void_p, []),
        "ZSTD_initDStream": (ctypes.c_size_t, [ctypes.c_void_p]),
        "ZSTD_freeDStream": (ctypes.c_size_t, [ctypes.c_void_p]),
        "ZSTD_decompressStream": (ctypes.c_size_t, [ctypes.c_void_p, ctypes.POINTER(OutputBuffer), ctypes.POINTER(InputBuffer)]),
        "ZSTD_isError": (ctypes.c_uint, [ctypes.c_size_t]),
        "ZSTD_getErrorName": (ctypes.c_char_p, [ctypes.c_size_t]),
        "ZSTD_compressBound": (ctypes.c_size_t, [ctypes.c_size_t]),
        "ZSTD_compress": (ctypes.c_size_t, [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int]),
    }
    for symbol, (result, arguments) in signatures.items():
        function = getattr(lib, symbol)
        function.restype, function.argtypes = result, arguments
    return lib


def checked(result):
    lib = library()
    if lib.ZSTD_isError(result):
        raise ValueError(lib.ZSTD_getErrorName(result).decode())
    return result


def decompress(data):
    lib = library()
    stream = lib.ZSTD_createDStream()
    if not stream:
        raise MemoryError("Cannot allocate zstd stream")
    source = ctypes.create_string_buffer(data)
    incoming = InputBuffer(ctypes.cast(source, ctypes.c_void_p), len(data), 0)
    result = bytearray()
    try:
        checked(lib.ZSTD_initDStream(stream))
        while True:
            storage = ctypes.create_string_buffer(131072)
            outgoing = OutputBuffer(ctypes.cast(storage, ctypes.c_void_p), len(storage), 0)
            previous = incoming.pos
            remaining = checked(lib.ZSTD_decompressStream(stream, ctypes.byref(outgoing), ctypes.byref(incoming)))
            result.extend(storage.raw[:outgoing.pos])
            if remaining == 0 and incoming.pos == incoming.size:
                return bytes(result)
            if previous == incoming.pos and outgoing.pos == 0:
                raise ValueError("Truncated zstd stream")
    finally:
        lib.ZSTD_freeDStream(stream)


def compress(data):
    lib = library()
    source = ctypes.create_string_buffer(data)
    capacity = lib.ZSTD_compressBound(len(data))
    target = ctypes.create_string_buffer(capacity)
    length = checked(lib.ZSTD_compress(target, capacity, source, len(data), 3))
    return target.raw[:length]


def read_events(path):
    for number, line in enumerate(decompress(path.read_bytes()).splitlines(), 1):
        if line.strip():
            try:
                yield json.loads(line)
            except (ValueError, UnicodeDecodeError) as error:
                raise ValueError(f"{path}:{number}: {error}") from error


def write_events(path, events):
    data = b"".join((json.dumps(event, separators=(",", ":")) + "\n").encode() for event in events)
    path.write_bytes(compress(data))
