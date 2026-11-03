import argparse
import contextlib
import logging
import os
import sys
import time
from collections import deque

import cv2
import numpy as np
import requests

from reconhecimento.pessoas import slug_pessoa
from reconhecimento.video.mjpeg import ExtratorMJPEG

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_DIR = os.path.join(BASE_DIR, "dataset")   

META_FOTOS_PADRAO = 40         
INTERVALO_MIN_CAPTURAS_S = 0.4  

HAAR_CASCADE_PATH = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("captura_dataset")


class FonteESP32Cam:
    def __init__(self, url: str, timeout: int = 10):
        self.url = url
        self._extrator = ExtratorMJPEG()
        self._prontos: deque[bytes] = deque()
        try:
            self._resposta = requests.get(url, stream=True, timeout=timeout)
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Não foi possível conectar em {url}: {e}") from e

        if self._resposta.status_code != 200:
            raise ConnectionError(
                f"ESP32-CAM respondeu com status HTTP {self._resposta.status_code} em {url}"
            )

        content_type = self._resposta.headers.get("Content-Type", "")
        if "multipart" not in content_type:
            self._resposta.close()
            raise ConnectionError(
                f"A resposta de {url} não é um stream de vídeo (Content-Type recebido: "
                f"'{content_type or 'nenhum'}'). Confira se a URL termina em '/stream', "
                f"ex.: http://SEU_IP_AQUI/stream"
            )

        self._iterador = self._resposta.iter_content(chunk_size=1024)

    def isOpened(self) -> bool:
        return bool(self._resposta) and self._resposta.ok

    def read(self):
        """Retorna (True, frame_bgr) ou (False, None), no padrão do OpenCV."""
        try:
            while True:
                while self._prontos:
                    frame = cv2.imdecode(np.frombuffer(self._prontos.popleft(), dtype=np.uint8), cv2.IMREAD_COLOR)
                    if frame is not None:
                        return True, frame

                pedaco = next(self._iterador, None)
                if pedaco is None:
                    return False, None
                self._prontos.extend(self._extrator.alimentar(pedaco))
        except (requests.exceptions.RequestException, StopIteration):
            return False, None

    def release(self):
        with contextlib.suppress(Exception):
            self._resposta.close()


class FonteESP32CamPolling:
    def __init__(self, capture_url: str, timeout: int = 5):
        self.capture_url = capture_url
        self.timeout = timeout
        self._testar_conexao()

    def _testar_conexao(self):
        try:
            resposta = requests.get(self.capture_url, timeout=self.timeout)
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Não foi possível conectar em {self.capture_url}: {e}") from e

        if resposta.status_code != 200:
            raise ConnectionError(
                f"ESP32-CAM respondeu com status HTTP {resposta.status_code} em {self.capture_url}"
            )

        content_type = resposta.headers.get("Content-Type", "")
        if "image" not in content_type:
            raise ConnectionError(
                f"A resposta de {self.capture_url} não é uma imagem (Content-Type recebido: "
                f"'{content_type or 'nenhum'}'). Confira se o firmware 'CameraWebServer.ino' "
                f"está rodando e se o endereço está correto."
            )

    def isOpened(self) -> bool:
        return True

    def read(self):
        """Retorna (True, frame_bgr) ou (False, None), no padrão do OpenCV."""
        try:
            resposta = requests.get(self.capture_url, timeout=self.timeout)
        except requests.exceptions.RequestException:
            return False, None

        if resposta.status_code != 200:
            return False, None

        frame = cv2.imdecode(np.frombuffer(resposta.content, dtype=np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            return False, None
        return True, frame

    def release(self):
        pass  


def _normalizar_url_base_esp32(esp32_url: str) -> str:
    """Remove sufixos /stream ou /capture eventualmente digitados, devolvendo só a raiz."""
    base = esp32_url.rstrip("/")
    for sufixo in ("/stream", "/capture"):
        if base.lower().endswith(sufixo):
            base = base[: -len(sufixo)]
    return base


def abrir_fonte_video(indice_camera: int, esp32_url: str, esp32_usar_stream: bool = False):
    """Abre a webcam local ou a câmera do ESP32-CAM, conforme os argumentos recebidos."""
    if esp32_url:
        base = _normalizar_url_base_esp32(esp32_url)
        if esp32_usar_stream:
            url, classe, modo = base + "/stream", FonteESP32Cam, "stream contínuo"
        else:
            url, classe, modo = base + "/capture", FonteESP32CamPolling, "captura por polling"

        logger.info("Conectando ao ESP32-CAM (%s) em %s ...", modo, url)
        try:
            fonte = classe(url)
        except ConnectionError as e:
            logger.error("Falha ao conectar no ESP32-CAM: %s", e)
            logger.error(
                "Verifique: (1) o firmware 'CameraWebServer.ino' está rodando; "
                "(2) o IP está correto (veja o Monitor Serial); "
                "(3) o computador está na mesma rede Wi-Fi do ESP32-CAM."
                + ("" if not esp32_usar_stream else " Se o problema persistir, tente sem a flag --esp32-stream.")
            )
            sys.exit(1)

        logger.info("Conectado ao ESP32-CAM com sucesso.")
        return fonte, False  # False = não espelhar (câmera fixa, não é "selfie")

    fonte = cv2.VideoCapture(indice_camera)
    if not fonte.isOpened():
        logger.error("Não foi possível acessar a câmera de índice %d.", indice_camera)
        sys.exit(1)
    return fonte, True  # True = espelha, mais natural para quem está de frente pro notebook


def melhorar_exibicao(frame_bgr):
    lab = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2LAB)
    canal_l, a, b = cv2.split(lab)
    clahe_cor = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l_realcado = clahe_cor.apply(canal_l)
    lab_realcado = cv2.merge((l_realcado, a, b))
    realcado = cv2.cvtColor(lab_realcado, cv2.COLOR_LAB2BGR)

    desfocado = cv2.GaussianBlur(realcado, (0, 0), sigmaX=3)
    nitido = cv2.addWeighted(realcado, 1.5, desfocado, -0.5, 0)
    return nitido


def expandir_caixa(caixa, largura_frame, altura_frame,
                    pad_horizontal=0.15, pad_topo=0.30, pad_base=0.10):
    x, y, w, h = caixa
    dx = int(w * pad_horizontal)
    dy_topo = int(h * pad_topo)
    dy_base = int(h * pad_base)

    novo_x = max(0, x - dx)
    novo_y = max(0, y - dy_topo)
    novo_w = min(largura_frame - novo_x, w + 2 * dx)
    novo_h = min(altura_frame - novo_y, h + dy_topo + dy_base)

    return (novo_x, novo_y, novo_w, novo_h)


def proximo_indice_arquivo(pasta_pessoa: str) -> int:
    """Permite continuar uma coleta anterior sem sobrescrever fotos já salvas."""
    existentes = [f for f in os.listdir(pasta_pessoa) if f.startswith("foto_") and f.endswith(".jpg")]
    if not existentes:
        return 1
    indices = []
    for f in existentes:
        try:
            indices.append(int(f.replace("foto_", "").replace(".jpg", "")))
        except ValueError:
            continue
    return (max(indices) + 1) if indices else 1

def capturar_dataset(nome_pessoa: str, meta_fotos: int, indice_camera: int, esp32_url: str = None, esp32_usar_stream: bool = False):
    pasta_pessoa = os.path.join(DATASET_DIR, slug_pessoa(nome_pessoa))
    os.makedirs(pasta_pessoa, exist_ok=True)

    proximo_indice = proximo_indice_arquivo(pasta_pessoa)
    ja_existentes = proximo_indice - 1
    if ja_existentes > 0:
        logger.info("Encontradas %d fotos existentes para '%s'. Continuando a coleta.", ja_existentes, nome_pessoa)

    face_cascade = cv2.CascadeClassifier(HAAR_CASCADE_PATH)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))  # contraste local, mais estável que equalizeHist simples

    captura, espelhar = abrir_fonte_video(indice_camera, esp32_url, esp32_usar_stream)

    if esp32_url:
        modo = "stream contínuo" if esp32_usar_stream else "polling /capture"
        fonte_descricao = f"ESP32-CAM ({esp32_url}, modo {modo})"
    else:
        fonte_descricao = f"webcam local (índice {indice_camera})"
    logger.info("Fonte de vídeo: %s", fonte_descricao)
    logger.info("Câmera iniciada. Posicione o rosto e pressione 'C' para capturar.")
    logger.info("Meta desta sessão: %d fotos. Pressione ESC para encerrar antes.", meta_fotos)

    fotos_capturadas_sessao = 0
    ultima_captura_ts = 0.0
    falhas_consecutivas = 0
    LIMITE_FALHAS_CONSECUTIVAS = 100  

    ultima_face_valida = None      
    frames_sem_deteccao = 0
    LIMITE_FRAMES_SEM_DETECCAO = 10  
    SUAVIZACAO_ALPHA = 0.4           

    janela = "Captura de Dataset - Reconhecimento Facial"
    cv2.namedWindow(janela)

    try:
        while fotos_capturadas_sessao < meta_fotos:
            ok, frame = captura.read()
            if not ok:
                falhas_consecutivas += 1
                if falhas_consecutivas == 1 or falhas_consecutivas % 25 == 0:
                    logger.warning("Falha ao ler frame da câmera (%d falhas consecutivas).", falhas_consecutivas)
                if falhas_consecutivas >= LIMITE_FALHAS_CONSECUTIVAS:
                    logger.error(
                        "%d falhas consecutivas ao ler frames - a conexão com a fonte de vídeo "
                        "parece ter caído (ESP32-CAM reiniciou? Wi-Fi caiu?). Encerrando a sessão.",
                        falhas_consecutivas,
                    )
                    break
                continue
            falhas_consecutivas = 0

            if espelhar:
                frame = cv2.flip(frame, 1)  
        
            frame_realcado = melhorar_exibicao(frame)

            cinza = cv2.cvtColor(frame_realcado, cv2.COLOR_BGR2GRAY)
            cinza_eq = clahe.apply(cinza)

            altura_frame, largura_frame = cinza_eq.shape[:2]
            tamanho_min_dinamico = (int(largura_frame * 0.15), int(altura_frame * 0.15))

            faces = face_cascade.detectMultiScale(
                cinza_eq,
                scaleFactor=1.08,
                minNeighbors=5,
                minSize=tamanho_min_dinamico,
            )

            exibicao = frame_realcado.copy()
            face_para_exibir = None

            if len(faces) > 0:
                faces_ordenadas = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
                nova_face = expandir_caixa(faces_ordenadas[0], largura_frame, altura_frame)

                if ultima_face_valida is None:
                    face_suavizada = nova_face
                else:
                    face_suavizada = tuple(
                        int(SUAVIZACAO_ALPHA * novo + (1 - SUAVIZACAO_ALPHA) * anterior)
                        for novo, anterior in zip(nova_face, ultima_face_valida, strict=True)
                    )

                ultima_face_valida = face_suavizada
                frames_sem_deteccao = 0
                rosto_detectado = True
                face_para_exibir = face_suavizada
                cor = (0, 200, 0)  

            elif ultima_face_valida is not None and frames_sem_deteccao < LIMITE_FRAMES_SEM_DETECCAO:
                frames_sem_deteccao += 1
                rosto_detectado = True
                face_para_exibir = ultima_face_valida
                cor = (0, 200, 200)  

            else:
                rosto_detectado = False
                ultima_face_valida = None
                cor = (0, 0, 255)  

            if face_para_exibir is not None:
                (x, y, w, h) = face_para_exibir
                cv2.rectangle(exibicao, (x, y), (x + w, y + h), cor, 2)

            status_rosto = "Rosto detectado - pronto para capturar" if rosto_detectado else "Nenhum rosto detectado"
            cv2.putText(exibicao, status_rosto, (15, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, cor, 2)
            cv2.putText(
                exibicao,
                f"Pessoa: {nome_pessoa}  |  Fotos: {fotos_capturadas_sessao}/{meta_fotos}",
                (15, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2,
            )
            cv2.putText(
                exibicao,
                "[C] ou [ESPACO] capturar   |   [ESC] encerrar",
                (15, exibicao.shape[0] - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1,
            )

            cv2.imshow(janela, exibicao)
            tecla = cv2.waitKey(1) & 0xFF

            if tecla == 27: 
                logger.info("Encerrado pelo usuário antes de atingir a meta.")
                break

            if tecla in (ord("c"), ord("C"), 32):  # C ou espaço
                agora = time.time()
                if agora - ultima_captura_ts < INTERVALO_MIN_CAPTURAS_S:
                    continue  

                if not rosto_detectado:
                    logger.warning("Nenhum rosto detectado no quadro atual - captura ignorada.")
                    continue

                caminho_arquivo = os.path.join(pasta_pessoa, f"foto_{proximo_indice:03d}.jpg")
                frame_para_salvar = cv2.flip(frame, 1) if espelhar else frame
                cv2.imwrite(caminho_arquivo, frame_para_salvar)

                proximo_indice += 1
                fotos_capturadas_sessao += 1
                ultima_captura_ts = agora
                logger.info("Foto %d/%d salva em %s", fotos_capturadas_sessao, meta_fotos, caminho_arquivo)

    finally:
        captura.release()
        cv2.destroyAllWindows()

    logger.info(
        "Sessão de captura concluída: %d fotos novas salvas em '%s'.",
        fotos_capturadas_sessao, pasta_pessoa,
    )
    if fotos_capturadas_sessao == 0:
        logger.warning("Nenhuma foto foi capturada nesta sessão.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Captura de imagens para o dataset de reconhecimento facial")
    parser.add_argument("--pessoa", type=str, default=None, help="Nome/identificador da pessoa a ser cadastrada")
    parser.add_argument("--meta", type=int, default=META_FOTOS_PADRAO, help="Quantidade de fotos a capturar (recomendado: 30 a 50)")
    parser.add_argument("--camera", type=int, default=0, help="Índice da webcam local a ser utilizada (padrão: 0). Ignorado se --esp32-url for informado.")
    parser.add_argument(
        "--esp32-url", type=str, default=None,
        help="Endereço base do ESP32-CAM em modo captura, ex.: http://192.168.0.55 "
             "(requer o firmware CameraWebServer.ino rodando no módulo). "
             "Não é necessário incluir /stream ou /capture - o script completa automaticamente.",
    )
    parser.add_argument(
        "--esp32-stream", action="store_true",
        help="Usa o stream MJPEG contínuo (/stream) em vez do modo padrão por polling (/capture). "
             "Mais fluido, porém mais sensível a instabilidades de rede/firmware.",
    )
    args = parser.parse_args()

    nome_pessoa = args.pessoa
    if not nome_pessoa:
        nome_pessoa = input("Nome da pessoa a ser cadastrada: ").strip()

    if not nome_pessoa:
        logger.error("Nome inválido. Encerrando.")
        sys.exit(1)

    if not (10 <= args.meta <= 200):
        logger.warning("Meta de fotos fora da faixa usual (10-200). Prosseguindo mesmo assim.")

    capturar_dataset(
        nome_pessoa, args.meta, args.camera,
        esp32_url=args.esp32_url, esp32_usar_stream=args.esp32_stream,
    )