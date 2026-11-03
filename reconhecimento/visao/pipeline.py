"""Pipeline de visão computacional: pré-processamento, Haar Cascade e LBPH."""

import json
import logging
import threading
from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np

from reconhecimento.config import Settings

logger = logging.getLogger(__name__)

TAMANHO_ROI = (200, 200)
Caixa = tuple[int, int, int, int]  # x, y, largura, altura

# Status produzidos pelo pipeline
AUTORIZADO = "authorized"
NEGADO = "denied"
REVOGADO = "revoked"
SEM_ROSTO = "no_face_detected"
ERRO = "error"
IMAGEM_INVALIDA = "invalid_image"


@dataclass
class ResultadoReconhecimento:
    """Resultado de uma tentativa de reconhecimento."""

    status: str
    user: str | None = None
    user_id: int | None = None
    confidence: float = 0.0
    distance_lbph: float | None = None
    message: str | None = None
    mensagem: str | None = None
    imagem_bgr: "np.ndarray | None" = None
    recorte_face: "np.ndarray | None" = None
    caixa: Caixa | None = None
    # Preenchidos pelo AcessoService ao registrar
    captura_id: int | None = None
    foto_path: str | None = None
    data_hora: str | None = None
    log_id: int | None = None

    def para_json(self) -> dict[str, Any]:
        """Resposta pública (sem matrizes do OpenCV)."""
        corpo: dict[str, Any] = {"status": self.status}
        if self.status in (AUTORIZADO, NEGADO, REVOGADO):
            corpo.update(
                user=self.user,
                user_id=self.user_id,
                confidence=self.confidence,
                distance_lbph=self.distance_lbph,
            )
        for chave in ("message", "mensagem", "captura_id"):
            valor = getattr(self, chave)
            if valor is not None:
                corpo[chave] = valor
        corpo.update(foto_path=self.foto_path, data_hora=self.data_hora, log_id=self.log_id)
        return corpo


class FaceRecognitionPipeline:
    """Detecta o rosto (Haar Cascade) e o classifica (LBPH)."""

    def __init__(self, settings: Settings):
        self._settings = settings
        caminho = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self._cascade = cv2.CascadeClassifier(caminho)
        if self._cascade.empty():
            raise RuntimeError(f"Não foi possível carregar o Haar Cascade em {caminho}")
        self._recognizer = cv2.face.LBPHFaceRecognizer_create()
        self._lock = threading.RLock()  # evita prever enquanto o modelo é recarregado
        self.labels: dict[int, str] = {}
        self.carregar_modelo()

    @property
    def modelo_carregado(self) -> bool:
        return bool(self.labels)

    def carregar_modelo(self) -> None:
        s = self._settings
        if not (s.model_path.exists() and s.labels_path.exists()):
            logger.warning("Modelo treinado não encontrado. O sistema operará aguardando treinamento.")
            return
        try:
            novo = cv2.face.LBPHFaceRecognizer_create()
            novo.read(str(s.model_path))
            with open(s.labels_path, encoding="utf-8") as f:
                labels = {int(k): v for k, v in json.load(f).items()}
            with self._lock:
                self._recognizer = novo
                self.labels = labels
            logger.info("Modelo LBPH carregado com sucesso (%d identidades).", len(labels))
        except (cv2.error, OSError, ValueError) as e:
            logger.error("Erro ao carregar modelo LBPH: %s", e)

    # --------------------------------------------------------------- etapas
    @staticmethod
    def pre_processar(imagem_bgr: "np.ndarray") -> "np.ndarray":
        cinza = cv2.cvtColor(imagem_bgr, cv2.COLOR_BGR2GRAY)
        cinza = cv2.equalizeHist(cinza)  # compensa variações de iluminação
        return cv2.GaussianBlur(cinza, (3, 3), 0)  # leve suavização de ruído

    def detectar_faces(self, cinza: "np.ndarray") -> list[Caixa]:
        faces = self._cascade.detectMultiScale(cinza, scaleFactor=1.1, minNeighbors=6, minSize=(80, 80))
        caixas = [(int(x), int(y), int(w), int(h)) for (x, y, w, h) in faces]
        return sorted(caixas, key=lambda c: c[2] * c[3], reverse=True)  # maior primeiro

    @staticmethod
    def recortar_normalizar(cinza: "np.ndarray", caixa: Caixa, tamanho: tuple[int, int] = TAMANHO_ROI) -> "np.ndarray":
        x, y, w, h = caixa
        return cv2.resize(cinza[y : y + h, x : x + w], tamanho, interpolation=cv2.INTER_LINEAR)

    def reconhecer(self, roi: "np.ndarray") -> tuple[int, float]:
        with self._lock:
            rotulo, distancia = self._recognizer.predict(roi)
        return int(rotulo), float(distancia)

    @staticmethod
    def _decodificar(imagem: bytes) -> "np.ndarray | None":
        """Decodifica JPEG/PNG; devolve None (nunca levanta) para bytes vazios, truncados ou corrompidos."""
        if not imagem:
            return None
        try:
            return cv2.imdecode(np.frombuffer(imagem, np.uint8), cv2.IMREAD_COLOR)
        except cv2.error:
            return None

    # ------------------------------------------------------------ principal
    def processar_imagem(self, imagem: bytes) -> ResultadoReconhecimento:
        imagem_bgr = self._decodificar(imagem)
        if imagem_bgr is None:
            return ResultadoReconhecimento(IMAGEM_INVALIDA, message="Imagem inválida ou corrompida.")

        cinza = self.pre_processar(imagem_bgr)
        faces = self.detectar_faces(cinza)
        if not faces:
            return ResultadoReconhecimento(SEM_ROSTO, imagem_bgr=imagem_bgr)

        caixa = faces[0]  # maior rosto = mais próximo da câmera
        x, y, w, h = caixa
        recorte = imagem_bgr[max(0, y) : min(imagem_bgr.shape[0], y + h), max(0, x) : min(imagem_bgr.shape[1], x + w)]

        if not self.labels:
            return ResultadoReconhecimento(ERRO, message="Modelo não treinado.", imagem_bgr=imagem_bgr, caixa=caixa)

        rotulo, distancia = self.reconhecer(self.recortar_normalizar(cinza, caixa))

        if distancia <= self._settings.lbph_threshold:
            # Pseudo-confiança apenas para leitura humana
            confianca = round(max(0.0, 1.0 - distancia / 100.0), 2)
            return ResultadoReconhecimento(
                AUTORIZADO,
                user=self.labels.get(rotulo, "desconhecido"),
                user_id=rotulo,
                confidence=confianca,
                distance_lbph=round(distancia, 2),
                imagem_bgr=imagem_bgr,
                recorte_face=recorte,
                caixa=caixa,
            )
        return ResultadoReconhecimento(
            NEGADO,
            distance_lbph=round(distancia, 2),
            imagem_bgr=imagem_bgr,
            recorte_face=recorte,
            caixa=caixa,
        )
