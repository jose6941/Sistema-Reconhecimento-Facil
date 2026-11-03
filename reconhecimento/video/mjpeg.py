"""Extração de frames JPEG de um stream MJPEG (marcadores SOI/EOI)."""

SOI = b"\xff\xd8"  # Start Of Image
EOI = b"\xff\xd9"  # End Of Image

LIMITE_BUFFER = 2_000_000
MANTER_AO_PODAR = 200_000


class ExtratorMJPEG:
    """Acumula bytes do stream e devolve os JPEGs completos já encontrados."""

    def __init__(self, limite_buffer: int = LIMITE_BUFFER, manter_ao_podar: int = MANTER_AO_PODAR):
        self._buffer = b""
        self._limite = limite_buffer
        self._manter = manter_ao_podar

    def alimentar(self, pedaco: bytes) -> list[bytes]:
        self._buffer += pedaco
        frames: list[bytes] = []

        while True:
            inicio = self._buffer.find(SOI)
            if inicio == -1:
                # Sem início de imagem: guarda só o último byte (um SOI pode estar partido ao meio).
                self._buffer = self._buffer[-1:]
                break
            fim = self._buffer.find(EOI, inicio + len(SOI))
            if fim == -1:
                self._buffer = self._buffer[inicio:]  # descarta lixo antes do SOI
                break
            frames.append(self._buffer[inicio : fim + len(EOI)])
            self._buffer = self._buffer[fim + len(EOI) :]

        if len(self._buffer) > self._limite:
            self._buffer = self._buffer[-self._manter :]
        return frames

    @property
    def tamanho_buffer(self) -> int:
        return len(self._buffer)
