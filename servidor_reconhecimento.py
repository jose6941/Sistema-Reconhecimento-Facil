"""
============================================================================
Sistema de Reconhecimento Facial de Baixo Custo - Servidor de Processamento
TCC - IFSP Câmpus Birigui
============================================================================

Recebe imagens enviadas pelo ESP32-CAM via HTTP POST (multipart/form-data),
executa o pipeline de visão computacional (pré-processamento, detecção facial
via Haar Cascade e reconhecimento via LBPH) e responde com um JSON indicando
se o acesso deve ser autorizado.

Disponibiliza também uma API REST completa e eventos em tempo real (SSE)
para integração com o painel web em Next.js (Abas: Ao vivo, Pessoas, Histórico).
"""

import os
import sys
import json
import logging
import argparse
import queue
import shutil
import threading
from datetime import datetime

import cv2
import numpy as np
from flask import Flask, request, jsonify, Response, send_from_directory
from flask_cors import CORS

import banco_dados

# --------------------------------------------------------------------------
# CONFIGURAÇÕES GERAIS E DIRETÓRIOS
# --------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_DIR = os.path.join(BASE_DIR, "dataset")          # dataset/<id>/*.jpg
MODEL_PATH = os.path.join(BASE_DIR, "modelo_lbph.yml")
LABELS_PATH = os.path.join(BASE_DIR, "labels.json")       # {"0": "Fulano", "1": "Ciclano"}

STATIC_DIR = os.path.join(BASE_DIR, "static")
DESCONHECIDOS_DIR = os.path.join(STATIC_DIR, "desconhecidos")
ACESSOS_DIR = os.path.join(STATIC_DIR, "acessos")

os.makedirs(DATASET_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(DESCONHECIDOS_DIR, exist_ok=True)
os.makedirs(ACESSOS_DIR, exist_ok=True)

# Limiar de confiança do LBPH: quanto MENOR o valor retornado pelo OpenCV,
# mais parecido é o rosto (é uma distância euclidiana/qui-quadrado, não probabilidade).
# Valores típicos calibrados: entre 55.0 e 70.0.
LBPH_CONFIDENCE_THRESHOLD = 65.0

HAAR_CASCADE_PATH = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("reconhecimento_facial")

app = Flask(__name__, static_folder="static", static_url_path="/static")
CORS(app)  # Permite requisições do frontend Next.js (port 3000)

# Fila para Server-Sent Events (SSE) para atualizar a aba "Ao vivo" em tempo real
eventos_clientes = []
ultimo_reconhecimento = {
    "status": "idle",
    "user": None,
    "user_id": None,
    "confidence": 0.0,
    "data_hora": None,
    "foto_url": None,
    "camera_id": "CAM-01 · Portaria",
}


def notificar_clientes_sse(evento: dict):
    """Envia um evento JSON para todos os navegadores conectados via Server-Sent Events."""
    for q in list(eventos_clientes):
        try:
            q.put_nowait(evento)
        except Exception:
            pass


# --------------------------------------------------------------------------
# PIPELINE DE VISÃO COMPUTACIONAL
# --------------------------------------------------------------------------
class FaceRecognitionPipeline:
    def __init__(self):
        self.face_cascade = cv2.CascadeClassifier(HAAR_CASCADE_PATH)
        self.recognizer = cv2.face.LBPHFaceRecognizer_create()
        self.labels = {}
        self._load_model()

    def _load_model(self):
        if os.path.exists(MODEL_PATH) and os.path.exists(LABELS_PATH):
            try:
                self.recognizer.read(MODEL_PATH)
                with open(LABELS_PATH, "r", encoding="utf-8") as f:
                    self.labels = {int(k): v for k, v in json.load(f).items()}
                logger.info("Modelo LBPH carregado com sucesso (%d identidades).", len(self.labels))
            except Exception as e:
                logger.error("Erro ao carregar modelo LBPH: %s", e)
        else:
            logger.warning(
                "Modelo treinado não encontrado. O sistema operará aguardando treinamento."
            )

    @staticmethod
    def preprocess(image_bgr):
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)  # equalização de histograma p/ variações de iluminação
        gray = cv2.GaussianBlur(gray, (3, 3), 0)  # leve suavização de ruído
        return gray

    def detect_faces(self, gray_image):
        faces = self.face_cascade.detectMultiScale(
            gray_image,
            scaleFactor=1.1,
            minNeighbors=6,
            minSize=(80, 80),
        )
        return faces

    @staticmethod
    def crop_and_normalize(gray_image, face_box, size=(200, 200)):
        (x, y, w, h) = face_box
        face_roi = gray_image[y:y + h, x:x + w]
        face_roi = cv2.resize(face_roi, size, interpolation=cv2.INTER_LINEAR)
        return face_roi

    def recognize(self, face_roi):
        label_id, confidence = self.recognizer.predict(face_roi)
        return label_id, confidence

    def process_image(self, image_bytes):
        np_arr = np.frombuffer(image_bytes, np.uint8)
        image_bgr = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if image_bgr is None:
            return {"status": "error", "message": "Imagem inválida ou corrompida."}

        gray = self.preprocess(image_bgr)
        faces = self.detect_faces(gray)

        if len(faces) == 0:
            return {
                "status": "no_face_detected",
                "image_bgr": image_bgr,
                "faces": [],
            }

        # Usa a maior face detectada (mais próxima da câmera)
        faces = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
        face_roi = self.crop_and_normalize(gray, faces[0])
        (x, y, w, h) = faces[0]

        # Recorte colorido da face para salvar em capturas
        face_color = image_bgr[max(0, y):min(image_bgr.shape[0], y + h), max(0, x):min(image_bgr.shape[1], x + w)]

        if not self.labels:
            return {
                "status": "error",
                "message": "Modelo não treinado.",
                "image_bgr": image_bgr,
                "box": (int(x), int(y), int(w), int(h)),
            }

        label_id, distance = self.recognize(face_roi)

        if distance <= LBPH_CONFIDENCE_THRESHOLD:
            user_name = self.labels.get(label_id, "desconhecido")
            # Normaliza a distância para uma pseudo-confiança percentual apenas p/ leitura humana
            pseudo_confidence = max(0.0, 1.0 - (distance / 100.0))
            return {
                "status": "authorized",
                "user": user_name,
                "user_id": int(label_id),
                "confidence": round(pseudo_confidence, 2),
                "distance_lbph": round(float(distance), 2),
                "image_bgr": image_bgr,
                "face_crop": face_color,
                "box": (int(x), int(y), int(w), int(h)),
            }
        else:
            return {
                "status": "denied",
                "user": None,
                "user_id": None,
                "confidence": 0.0,
                "distance_lbph": round(float(distance), 2),
                "image_bgr": image_bgr,
                "face_crop": face_color,
                "box": (int(x), int(y), int(w), int(h)),
            }


pipeline = FaceRecognitionPipeline()


# --------------------------------------------------------------------------
# WORKER DE PROCESSAMENTO CONTÍNUO VIA STREAM DO ESP32-CAM
# --------------------------------------------------------------------------
import time
import requests


class ESP32StreamWorker:
    """
    Consome o stream MJPEG contínuo do ESP32-CAM em segundo plano,
    detecta aproximação de pessoas, aplica o reconhecimento facial LBPH,
    executa debounce anti-spam para não sobrecarregar os logs e
    notifica a interface web Next.js via Server-Sent Events (SSE).
    """

    def __init__(self):
        self.running = False
        self.url = None
        self.thread = None
        self.fps = 0.0
        self.last_frame_ts = None
        self.last_log_time = {}  # {user_key: timestamp}
        self.debounce_seconds = 4.0  # Tempo mínimo entre registros da mesma pessoa

    def conectar(self, base_url: str):
        self.desconectar()
        base = base_url.strip().rstrip("/")
        if not base.startswith("http"):
            base = "http://" + base

        if base.endswith("/stream") or base.endswith("/capture"):
            self.url = base
        else:
            self.url = base + "/stream"

        self.running = True
        self.thread = threading.Thread(target=self._loop_stream, daemon=True)
        self.thread.start()
        logger.info("Worker de Stream ESP32-CAM iniciado para: %s", self.url)

    def desconectar(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.5)
        self.thread = None
        self.url = None
        self.fps = 0.0
        logger.info("Worker de Stream ESP32-CAM desconectado.")

    def obter_status(self):
        return {
            "conectado": self.running and bool(self.thread and self.thread.is_alive()),
            "url": self.url,
            "fps": self.fps,
            "ultimo_frame_ts": self.last_frame_ts,
        }

    def _loop_stream(self):
        buffer = b""
        frames_count = 0
        fps_start = time.time()
        falhas_consecutivas = 0

        while self.running:
            try:
                logger.info("Conectando ao stream do ESP32 em %s ...", self.url)
                resp = requests.get(self.url, stream=True, timeout=8)
                if resp.status_code != 200:
                    falhas_consecutivas += 1
                    time.sleep(2)
                    continue

                falhas_consecutivas = 0
                for chunk in resp.iter_content(chunk_size=2048):
                    if not self.running:
                        break
                    buffer += chunk
                    inicio = buffer.find(b"\xff\xd8")  # JPEG SOI
                    fim = buffer.find(b"\xff\xd9")     # JPEG EOI

                    if inicio != -1 and fim != -1 and fim > inicio:
                        jpg_bytes = buffer[inicio:fim + 2]
                        buffer = buffer[fim + 2:]

                        self._processar_frame(jpg_bytes)
                        frames_count += 1
                        agora = time.time()
                        if agora - fps_start >= 2.0:
                            self.fps = round(frames_count / (agora - fps_start), 1)
                            frames_count = 0
                            fps_start = agora

                    if len(buffer) > 2_000_000:
                        buffer = buffer[-200_000:]
                resp.close()
            except Exception as e:
                falhas_consecutivas += 1
                if falhas_consecutivas % 10 == 1:
                    logger.warning("Instabilidade na conexão com o stream do ESP32 (%s): %s", self.url, e)
                time.sleep(1.5)

    def _processar_frame(self, jpg_bytes: bytes):
        agora = time.time()
        agora_iso = datetime.now().isoformat(timespec="seconds")
        self.last_frame_ts = agora_iso

        resultado = pipeline.process_image(jpg_bytes)
        status = resultado.get("status")

        if status == "no_face_detected":
            # Atualiza o último frame da câmera para a tela Ao vivo mesmo sem rosto
            if "image_bgr" in resultado and resultado["image_bgr"] is not None:
                cv2.imwrite(os.path.join(STATIC_DIR, "ultimo_frame.jpg"), resultado["image_bgr"])
            return

        # Rosto detectado no frame!
        if status == "authorized":
            u_id = resultado.get("user_id")
            user_status = banco_dados.obter_status_usuario(u_id)
            if user_status == "revogado":
                status = "revoked"
                resultado["status"] = "revoked"
                resultado["mensagem"] = "Acesso negado: Usuário com permissão revogada!"

        # Atualiza a imagem com bounding box da face detectada
        if "image_bgr" in resultado and resultado["image_bgr"] is not None:
            frame_box = resultado["image_bgr"].copy()
            if "box" in resultado:
                (x, y, w, h) = resultado["box"]
                cor = (0, 200, 0) if status == "authorized" else (0, 0, 255)
                cv2.rectangle(frame_box, (x, y), (x + w, y + h), cor, 2)
                rotulo = f"{resultado.get('user') or 'Desconhecido'} ({resultado.get('confidence', 0)*100:.0f}%)"
                cv2.putText(frame_box, rotulo, (x, max(25, y - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, cor, 2)
            cv2.imwrite(os.path.join(STATIC_DIR, "ultimo_frame.jpg"), frame_box)

        # Anti-spam / Debounce: evita registrar múltiplos acessos no mesmo segundo para a mesma pessoa
        chave_debounce = resultado.get("user") or f"status_{status}"
        ultimo_ts = self.last_log_time.get(chave_debounce, 0.0)

        if agora - ultimo_ts >= self.debounce_seconds:
            self.last_log_time[chave_debounce] = agora
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            foto_rel_path = None

            if status == "denied":
                if "face_crop" in resultado and resultado["face_crop"] is not None and resultado["face_crop"].size > 0:
                    filename = f"desconhecido_{timestamp_str}.jpg"
                    filepath = os.path.join(DESCONHECIDOS_DIR, filename)
                    cv2.imwrite(filepath, resultado["face_crop"])
                    foto_rel_path = f"/static/desconhecidos/{filename}"

                    captura_id = banco_dados.salvar_captura_desconhecida(foto_rel_path)
                    resultado["captura_id"] = captura_id
                    resultado["user"] = f"Desconhecido #{captura_id}"
                else:
                    resultado["user"] = "Desconhecido"

            elif status in ("authorized", "revoked"):
                if "face_crop" in resultado and resultado["face_crop"] is not None and resultado["face_crop"].size > 0:
                    filename = f"acesso_{timestamp_str}.jpg"
                    filepath = os.path.join(ACESSOS_DIR, filename)
                    cv2.imwrite(filepath, resultado["face_crop"])
                    foto_rel_path = f"/static/acessos/{filename}"

            log_id = banco_dados.registrar_log(
                usuario_id=resultado.get("user_id"),
                usuario_nome=resultado.get("user"),
                status=status,
                confianca=resultado.get("confidence", 0.0),
                distancia_lbph=resultado.get("distance_lbph"),
                foto_path=foto_rel_path,
            )

            global ultimo_reconhecimento
            ultimo_reconhecimento = {
                "status": status,
                "user": resultado.get("user"),
                "user_id": resultado.get("user_id"),
                "confidence": resultado.get("confidence", 0.0),
                "distance_lbph": resultado.get("distance_lbph"),
                "data_hora": agora_iso,
                "foto_url": foto_rel_path,
                "camera_id": "CAM-01 · Portaria",
            }

            notificar_clientes_sse({
                "tipo": "novo_acesso",
                "dados": {
                    "id": log_id,
                    "data_hora": agora_iso,
                    "usuario_nome": resultado.get("user"),
                    "status": status,
                    "confianca": resultado.get("confidence", 0.0),
                    "distancia_lbph": resultado.get("distance_lbph"),
                    "foto_path": foto_rel_path,
                },
            })

            logger.info("[Stream Auto-Log] %s -> %s", resultado.get("user"), status)


stream_worker = ESP32StreamWorker()


# --------------------------------------------------------------------------
# ROTAS PRINCIPAIS DE RECONHECIMENTO (ESP32-CAM)
# --------------------------------------------------------------------------
@app.route("/reconhecer", methods=["POST"])
def reconhecer():
    """
    Recebe imagem do ESP32-CAM via POST multipart/form-data.
    Executa o pipeline, valida revogações, salva recortes se necessário,
    grava no log do SQLite e notifica a interface web via SSE.
    """
    if "imagem" not in request.files:
        return jsonify({"status": "error", "message": "Campo 'imagem' ausente."}), 400

    file = request.files["imagem"]
    image_bytes = file.read()

    if not image_bytes:
        return jsonify({"status": "error", "message": "Arquivo de imagem vazio."}), 400

    resultado = pipeline.process_image(image_bytes)
    status = resultado.get("status")

    # 1. Regra de Negócio: Verificação de Revogação de Acesso
    if status == "authorized":
        u_id = resultado.get("user_id")
        user_status = banco_dados.obter_status_usuario(u_id)
        if user_status == "revogado":
            resultado["status"] = "revoked"
            status = "revoked"
            resultado["mensagem"] = "Acesso negado: Usuário com permissão revogada!"

    # 2. Armazenamento de Fotos e Recortes
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    foto_rel_path = None

    if status == "denied":
        # Salva o recorte da face não identificada para permitir vinculação posterior na aba Pessoas
        if "face_crop" in resultado and resultado["face_crop"] is not None and resultado["face_crop"].size > 0:
            filename = f"desconhecido_{timestamp_str}.jpg"
            filepath = os.path.join(DESCONHECIDOS_DIR, filename)
            cv2.imwrite(filepath, resultado["face_crop"])
            foto_rel_path = f"/static/desconhecidos/{filename}"

            captura_id = banco_dados.salvar_captura_desconhecida(foto_rel_path)
            resultado["captura_id"] = captura_id
            resultado["user"] = f"Desconhecido #{captura_id}"
        else:
            resultado["user"] = "Desconhecido"

    elif status in ("authorized", "revoked"):
        if "face_crop" in resultado and resultado["face_crop"] is not None and resultado["face_crop"].size > 0:
            filename = f"acesso_{timestamp_str}.jpg"
            filepath = os.path.join(ACESSOS_DIR, filename)
            cv2.imwrite(filepath, resultado["face_crop"])
            foto_rel_path = f"/static/acessos/{filename}"

    # Salva o último frame com bounding box para visualização ao vivo no Next.js
    if "image_bgr" in resultado and resultado["image_bgr"] is not None:
        frame_box = resultado["image_bgr"].copy()
        if "box" in resultado:
            (x, y, w, h) = resultado["box"]
            cor = (0, 200, 0) if status == "authorized" else (0, 0, 255)
            cv2.rectangle(frame_box, (x, y), (x + w, y + h), cor, 2)
            cv2.putText(
                frame_box,
                f"{resultado.get('user') or 'Desconhecido'} ({resultado.get('confidence', 0)*100:.0f}%)",
                (x, max(25, y - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                cor,
                2,
            )
        cv2.imwrite(os.path.join(STATIC_DIR, "ultimo_frame.jpg"), frame_box)

    resultado["foto_path"] = foto_rel_path
    agora_iso = datetime.now().isoformat(timespec="seconds")
    resultado["data_hora"] = agora_iso

    # 3. Registra no banco de dados SQLite
    log_id = banco_dados.registrar_log(
        usuario_id=resultado.get("user_id"),
        usuario_nome=resultado.get("user"),
        status=resultado.get("status", "error"),
        confianca=resultado.get("confidence", 0.0),
        distancia_lbph=resultado.get("distance_lbph"),
        foto_path=foto_rel_path,
    )
    resultado["log_id"] = log_id

    # 4. Atualiza estado em memória para a tela Ao vivo
    global ultimo_reconhecimento
    ultimo_reconhecimento = {
        "status": resultado.get("status"),
        "user": resultado.get("user"),
        "user_id": resultado.get("user_id"),
        "confidence": resultado.get("confidence", 0.0),
        "distance_lbph": resultado.get("distance_lbph"),
        "data_hora": agora_iso,
        "foto_url": foto_rel_path,
        "camera_id": "CAM-01 · Portaria",
    }

    # 5. Notifica o frontend Next.js via Server-Sent Events (SSE)
    notificar_clientes_sse({
        "tipo": "novo_acesso",
        "dados": {
            "id": log_id,
            "data_hora": agora_iso,
            "usuario_nome": resultado.get("user"),
            "status": resultado.get("status"),
            "confianca": resultado.get("confidence", 0.0),
            "distancia_lbph": resultado.get("distance_lbph"),
            "foto_path": foto_rel_path,
        },
    })

    logger.info("Reconhecimento concluído: %s -> %s", resultado.get("user"), resultado.get("status"))

    # Retorna JSON limpo (sem matrizes do OpenCV)
    resposta = {k: v for k, v in resultado.items() if k not in ("image_bgr", "face_crop", "box")}
    return jsonify(resposta), 200


@app.route("/saude", methods=["GET"])
def saude():
    """Endpoint leve de verificação de disponibilidade."""
    return jsonify({"status": "ok", "modelo_carregado": bool(pipeline.labels)}), 200


# --------------------------------------------------------------------------
# API REST PARA O FRONTEND NEXT.JS
# --------------------------------------------------------------------------
@app.route("/api/status", methods=["GET"])
def api_status():
    """Retorna o estado global do sistema para a barra de cabeçalho do Next.js."""
    return jsonify({
        "status": "online",
        "modelo_carregado": bool(pipeline.labels),
        "total_identidades": len(pipeline.labels),
        "limiar_lbph": LBPH_CONFIDENCE_THRESHOLD,
        "camera_id": "CAM-01 · Portaria",
        "ultimo_reconhecimento": ultimo_reconhecimento,
    }), 200


@app.route("/api/eventos", methods=["GET"])
def api_eventos():
    """
    Endpoint Server-Sent Events (SSE). Permite que o Next.js receba notificações
    automáticas em tempo real a cada novo acesso detectado pela câmera.
    """
    def gerador():
        q = queue.Queue(maxsize=30)
        eventos_clientes.append(q)
        try:
            # Envia estado inicial ao conectar
            yield f"data: {json.dumps({'tipo': 'init', 'dados': ultimo_reconhecimento})}\n\n"
            while True:
                try:
                    evento = q.get(timeout=25)
                    yield f"data: {json.dumps(evento)}\n\n"
                except queue.Empty:
                    # Ping periódico para manter a conexão HTTP ativa
                    yield ": ping\n\n"
        except GeneratorExit:
            pass
        finally:
            if q in eventos_clientes:
                eventos_clientes.remove(q)

    return Response(gerador(), mimetype="text/event-stream")


@app.route("/api/logs", methods=["GET"])
def api_logs():
    """Retorna o histórico de acessos com filtros opcionais."""
    usuario_nome = request.args.get("usuario")
    status = request.args.get("status")
    data_inicio = request.args.get("data_inicio")
    data_fim = request.args.get("data_fim")
    limite = int(request.args.get("limite", 100))

    logs = banco_dados.consultar_logs(
        usuario_nome=usuario_nome,
        status=status,
        data_inicio=data_inicio,
        data_fim=data_fim,
        limite=limite,
    )
    return jsonify(logs), 200


@app.route("/api/logs/recentes", methods=["GET"])
def api_logs_recentes():
    """Retorna os últimos acessos para a lista 'Registro de entradas' da tela Ao vivo."""
    limite = int(request.args.get("limite", 15))
    logs = banco_dados.consultar_logs(limite=limite)
    return jsonify(logs), 200


@app.route("/api/logs/excecoes", methods=["GET"])
def api_logs_excecoes():
    """Retorna apenas as exceções (negados, revogados e desconhecidos) para a tela Histórico."""
    limite = int(request.args.get("limite", 15))
    excecoes = banco_dados.listar_excecoes(limite=limite)
    return jsonify(excecoes), 200


@app.route("/api/usuarios", methods=["GET"])
def api_usuarios():
    """Retorna a lista de pessoas cadastradas com métricas para a tela Pessoas."""
    usuarios = banco_dados.listar_usuarios()

    # Adiciona a contagem de fotos do dataset para cada usuário
    for u in usuarios:
        nome_pasta = u["nome"].strip().lower().replace(" ", "_")
        pasta = os.path.join(DATASET_DIR, nome_pasta)
        if os.path.isdir(pasta):
            fotos = [f for f in os.listdir(pasta) if f.lower().endswith((".jpg", ".png", ".jpeg"))]
            u["total_fotos"] = len(fotos)
        else:
            u["total_fotos"] = 0

    return jsonify(usuarios), 200


@app.route("/api/usuarios/<int:usuario_id>/status", methods=["PATCH"])
def api_atualizar_status_usuario(usuario_id: int):
    """Altera o status de uma pessoa entre 'ativo' e 'revogado'."""
    dados = request.get_json(silent=True) or {}
    novo_status = dados.get("status")

    if novo_status not in ("ativo", "revogado"):
        return jsonify({"erro": "Status inválido. Use 'ativo' ou 'revogado'."}), 400

    try:
        banco_dados.atualizar_status_usuario(usuario_id, novo_status)
        return jsonify({"sucesso": True, "usuario_id": usuario_id, "novo_status": novo_status}), 200
    except Exception as e:
        return jsonify({"erro": str(e)}), 500


@app.route("/api/capturas-desconhecidas", methods=["GET"])
def api_capturas_desconhecidas():
    """Retorna capturas de faces não identificadas para o bloco 'Capturas sem cadastro'."""
    capturas = banco_dados.listar_capturas_desconhecidas(apenas_pendentes=True)
    return jsonify(capturas), 200


@app.route("/api/vincular-captura", methods=["POST"])
def api_vincular_captura():
    """
    Vincula uma captura sem cadastro (#12) a uma pessoa (existente ou nova),
    copiando a imagem para a pasta do dataset correspondente e agendando retreino.
    """
    dados = request.get_json(silent=True) or {}
    captura_id = dados.get("captura_id")
    nome_pessoa = (dados.get("nome_pessoa") or "").strip()

    if not captura_id or not nome_pessoa:
        return jsonify({"erro": "Campos 'captura_id' e 'nome_pessoa' são obrigatórios."}), 400

    # Busca a captura no banco
    capturas = banco_dados.listar_capturas_desconhecidas(apenas_pendentes=False, limite=500)
    captura_encontrada = next((c for c in capturas if c["id"] == int(captura_id)), None)

    if not captura_encontrada:
        return jsonify({"erro": "Captura não encontrada."}), 404

    # Pasta de destino no dataset
    nome_pasta = nome_pessoa.lower().replace(" ", "_")
    nome_pasta = "".join(c for c in nome_pasta if c.isalnum() or c == "_")
    pasta_destino = os.path.join(DATASET_DIR, nome_pasta)
    os.makedirs(pasta_destino, exist_ok=True)

    # Copia o arquivo da captura para o dataset
    caminho_rel = captura_encontrada["caminho_foto"].lstrip("/")
    caminho_origem = os.path.join(BASE_DIR, caminho_rel.replace("/", os.sep))

    if os.path.isfile(caminho_origem):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        novo_arquivo = f"vinculado_{captura_id}_{timestamp}.jpg"
        shutil.copy2(caminho_origem, os.path.join(pasta_destino, novo_arquivo))

    # Marca como resolvida no banco
    banco_dados.resolver_captura_desconhecida(captura_id, usuario_id=0)

    # Dispara o retreinamento do modelo em segundo plano
    threading.Thread(target=treinar_modelo, daemon=True).start()

    return jsonify({
        "sucesso": True,
        "mensagem": f"Captura #{captura_id} vinculada a '{nome_pessoa}'. Retreinamento iniciado!",
    }), 200


@app.route("/api/treinar", methods=["POST"])
def api_treinar():
    """Dispara o treinamento do classificador LBPH em segundo plano a partir da web."""
    threading.Thread(target=treinar_modelo, daemon=True).start()
    return jsonify({"sucesso": True, "mensagem": "Treinamento do modelo LBPH iniciado."}), 200


@app.route("/api/estatisticas", methods=["GET"])
def api_estatisticas():
    """Retorna os dados numéricos para os 3 cards do topo da tela Histórico."""
    stats = banco_dados.obter_estatisticas_historico()
    return jsonify(stats), 200


@app.route("/api/camera/ultimo-frame", methods=["GET"])
def api_ultimo_frame():
    """Retorna a última imagem processada pela câmera com bounding box."""
    caminho_frame = os.path.join(STATIC_DIR, "ultimo_frame.jpg")
    if os.path.isfile(caminho_frame):
        return send_from_directory(STATIC_DIR, "ultimo_frame.jpg")
    # Imagem padrão caso ainda não haja capturas
    return send_from_directory(STATIC_DIR, "placeholder.jpg") if os.path.isfile(
        os.path.join(STATIC_DIR, "placeholder.jpg")
    ) else ("", 204)


@app.route("/api/simular-leitura", methods=["POST"])
def api_simular_leitura():
    """
    Permite simular uma tentativa de acesso pela interface web.
    Recurso essencial para testar e demonstrar o sistema perante a banca do TCC
    sem depender da câmera física ou da rede Wi-Fi do local da apresentação.
    """
    dados = request.get_json(silent=True) or {}
    tipo = dados.get("tipo", "autorizado")  # autorizado, negado, revogado, desconhecido
    nome = dados.get("nome", "Marina Costa")

    agora = datetime.now().isoformat(timespec="seconds")
    global ultimo_reconhecimento

    if tipo == "autorizado":
        confianca = 0.96
        distancia = 38.4
        status = "authorized"
        usuario_nome = nome
        usuario_id = 1
    elif tipo == "revogado":
        confianca = 0.94
        distancia = 42.1
        status = "revoked"
        usuario_nome = nome if nome != "Marina Costa" else "Sérgio Baptista"
        usuario_id = 2
    else:  # negado / desconhecido
        confianca = 0.0
        distancia = 88.7
        status = "denied"
        # Cria uma captura desconhecida simulada
        captura_id = banco_dados.salvar_captura_desconhecida("/static/desconhecidos/simulacao.jpg")
        usuario_nome = f"Desconhecido #{captura_id}"
        usuario_id = None

    log_id = banco_dados.registrar_log(
        usuario_id=usuario_id,
        usuario_nome=usuario_nome,
        status=status,
        confianca=confianca,
        distancia_lbph=distancia,
    )

    ultimo_reconhecimento = {
        "status": status,
        "user": usuario_nome,
        "user_id": usuario_id,
        "confidence": confianca,
        "distance_lbph": distancia,
        "data_hora": agora,
        "foto_url": None,
        "camera_id": "CAM-01 · Portaria",
    }

    notificar_clientes_sse({
        "tipo": "novo_acesso",
        "dados": {
            "id": log_id,
            "data_hora": agora,
            "usuario_nome": usuario_nome,
            "status": status,
            "confianca": confianca,
            "distancia_lbph": distancia,
            "foto_path": None,
        },
    })

    return jsonify({"sucesso": True, "simulacao": ultimo_reconhecimento}), 200


# --------------------------------------------------------------------------
# TREINAMENTO DO MODELO (a partir de ./dataset/<id_pessoa>/*.jpg)
# --------------------------------------------------------------------------
def treinar_modelo():
    """
    Treina o modelo LBPH com base nas imagens em ./dataset/<nome_pessoa>/*.jpg.
    Atualiza modelo_lbph.yml, labels.json, sincroniza o banco e recarrega o pipeline.
    """
    if not os.path.isdir(DATASET_DIR):
        logger.error("Diretório de dataset não encontrado: %s", DATASET_DIR)
        return False

    face_cascade = cv2.CascadeClassifier(HAAR_CASCADE_PATH)
    recognizer = cv2.face.LBPHFaceRecognizer_create()

    MINIMO_FOTOS_RECOMENDADO = 15

    faces_treino = []
    ids_treino = []
    labels = {}
    resumo_por_pessoa = []
    next_id = 0

    pastas = sorted(os.listdir(DATASET_DIR))
    if not pastas:
        logger.warning("Nenhuma pasta de usuário encontrada em %s", DATASET_DIR)
        return False

    for pessoa in pastas:
        pessoa_dir = os.path.join(DATASET_DIR, pessoa)
        if not os.path.isdir(pessoa_dir):
            continue

        # Nome limpo para exibição
        nome_exibicao = pessoa.replace("_", " ").title()
        labels[next_id] = nome_exibicao
        logger.info("Processando imagens de '%s' (id=%d)...", nome_exibicao, next_id)

        arquivos = [f for f in os.listdir(pessoa_dir) if f.lower().endswith((".jpg", ".jpeg", ".png"))]
        total_fotos = len(arquivos)
        fotos_aproveitadas = 0

        for arquivo in arquivos:
            caminho = os.path.join(pessoa_dir, arquivo)
            img = cv2.imread(caminho)
            if img is None:
                continue

            gray = FaceRecognitionPipeline.preprocess(img)
            faces = face_cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=6, minSize=(80, 80)
            )

            if len(faces) == 0:
                continue

            faces_ordenadas = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
            roi = FaceRecognitionPipeline.crop_and_normalize(gray, faces_ordenadas[0])
            faces_treino.append(roi)
            ids_treino.append(next_id)
            fotos_aproveitadas += 1

        resumo_por_pessoa.append((nome_exibicao, total_fotos, fotos_aproveitadas))
        next_id += 1

    if not faces_treino:
        logger.warning("Nenhuma face válida encontrada no dataset para treinamento.")
        return False

    recognizer.train(faces_treino, np.array(ids_treino))
    recognizer.write(MODEL_PATH)

    with open(LABELS_PATH, "w", encoding="utf-8") as f:
        json.dump(labels, f, ensure_ascii=False, indent=2)

    # Sincroniza a tabela usuarios do banco de dados SQLite
    banco_dados.salvar_usuarios(labels)

    # Recarrega o pipeline na memória do servidor sem precisar reiniciar o processo Flask
    pipeline._load_model()

    logger.info("--- Treinamento Concluído com Sucesso ---")
    for nome, total, aprov in resumo_por_pessoa:
        logger.info("  %-25s %3d/%3d fotos aproveitadas", nome, aprov, total)

    notificar_clientes_sse({
        "tipo": "treinamento_concluido",
        "dados": {"total_identidades": len(labels), "total_amostras": len(faces_treino)},
    })

    return True


@app.route("/api/camera/conectar", methods=["POST"])
def api_camera_conectar():
    """Inicia o consumo contínuo do stream do ESP32-CAM."""
    dados = request.get_json(silent=True) or {}
    url = dados.get("url")
    if not url:
        return jsonify({"erro": "Campo 'url' é obrigatório (ex: http://192.168.0.55)."}), 400

    stream_worker.conectar(url)
    return jsonify({"sucesso": True, "status": stream_worker.obter_status()}), 200


@app.route("/api/camera/desconectar", methods=["POST"])
def api_camera_desconectar():
    """Encerra o consumo do stream do ESP32-CAM."""
    stream_worker.desconectar()
    return jsonify({"sucesso": True, "status": stream_worker.obter_status()}), 200


@app.route("/api/camera/info", methods=["GET"])
def api_camera_info():
    """Retorna o estado da conexão e FPS com a câmera ESP32-CAM."""
    return jsonify(stream_worker.obter_status()), 200


# --------------------------------------------------------------------------
# INICIALIZAÇÃO
# --------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Servidor de reconhecimento facial")
    parser.add_argument("--train", action="store_true", help="Treina o modelo LBPH a partir do dataset")
    parser.add_argument("--serve", action="store_true", help="Sobe o servidor Flask")
    parser.add_argument("--esp32-url", default=None, help="Conecta automaticamente ao stream do ESP32-CAM (ex: http://192.168.0.55)")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", default=5000, type=int)
    args = parser.parse_args()

    banco_dados.inicializar_banco()

    if args.train:
        treinar_modelo()
    elif args.serve or not args.train:
        if args.esp32_url:
            logger.info("Iniciando conexão automática com o ESP32-CAM em %s ...", args.esp32_url)
            stream_worker.conectar(args.esp32_url)

        logger.info("Iniciando Servidor Flask em http://%s:%d ...", args.host, args.port)
        app.run(host=args.host, port=args.port, debug=False, threaded=True)