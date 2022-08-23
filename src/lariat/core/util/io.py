from __future__ import annotations

import io
import itertools


class GeneratorBytestIO(io.BufferedIOBase):
    def __init__(self, generator):
        self._iter = itertools.chain.from_iterable(generator)

    def read(self, __size: int | None = ...) -> bytes:
        return bytes(itertools.islice(self._iter, __size))
