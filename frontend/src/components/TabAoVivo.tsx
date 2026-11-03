"use client";

import { useCallback, useEffect, useState } from "react";
import { IconCamera, IconRefresh, IconWifi, IconWifiOff } from "@tabler/icons-react";
import { Modal } from "@/components/Modal";
import { StatusBadge } from "@/components/StatusBadge";
import { formatarConfianca, formatarHora } from "@/lib/formatadores";
import { COR_PONTO, infoStatus } from "@/lib/status";
import { api, API_BASE_URL, InfoCamera, LogAcesso, StatusSistema } from "@/services/api";

interface TabAoVivoProps {
  statusSistema: StatusSistema | null;
  logs: LogAcesso[];
  onRefresh: () => void;
}

const INTERVALO_FRAME_MS = 500;
const CAMERA_PADRAO = "CAM-01 · Portaria";

export function TabAoVivo({ statusSistema, logs, onRefresh }: TabAoVivoProps) {
  // Começa em 0 (igual no servidor e no navegador, evitando erro de hidratação);
  // o intervalo abaixo troca por Date.now() a cada 500 ms para não usar cache.
  const [frameKey, setFrameKey] = useState(0);
  const [imgErro, setImgErro] = useState(false);

  const [cameraInfo, setCameraInfo] = useState<Pick<InfoCamera, "conectado" | "url" | "fps">>({
    conectado: false,
    url: null,
    fps: 0,
  });
  const [modalConexao, setModalConexao] = useState(false);
  const [urlEsp32, setUrlEsp32] = useState("http://192.168.0.55");
  const [conectando, setConectando] = useState(false);
  const [erroConexao, setErroConexao] = useState<string | null>(null);

  const ultimo = statusSistema?.ultimo_reconhecimento;
  const cameraId = statusSistema?.camera_id ?? CAMERA_PADRAO;
  const aguardando = !ultimo || ultimo.status === "idle" || !ultimo.data_hora;

  const atualizarStatusCamera = useCallback(async () => {
    try {
      const info = await api.getCameraInfo();
      setCameraInfo(info);
      if (info.url) setUrlEsp32(info.url.replace("/stream", "").replace("/capture", ""));
    } catch {
      // Backend offline: mantém o último estado conhecido
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- sincroniza com o estado da câmera no backend
    atualizarStatusCamera();
    const timer = setInterval(() => {
      atualizarStatusCamera();
      setFrameKey(Date.now());
    }, INTERVALO_FRAME_MS);
    return () => clearInterval(timer);
  }, [atualizarStatusCamera]);

  const handleConectarCamera = async () => {
    if (!urlEsp32.trim()) return;
    setConectando(true);
    setErroConexao(null);
    try {
      await api.conectarCamera(urlEsp32.trim());
      await atualizarStatusCamera();
      setImgErro(false);
      setModalConexao(false);
    } catch (e) {
      console.error("Erro ao conectar câmera:", e);
      setErroConexao("Endereço recusado ou servidor indisponível. Use um endereço http:// ou https:// válido.");
    } finally {
      setConectando(false);
    }
  };

  const handleDesconectarCamera = async () => {
    try {
      await api.desconectarCamera();
      await atualizarStatusCamera();
    } catch (e) {
      console.error("Erro ao desconectar câmera:", e);
    }
  };

  const legendaCamera = () => {
    if (aguardando) {
      return cameraInfo.conectado
        ? `ESP32 Conectado (${cameraInfo.fps} FPS) · Aguardando aproximação de pessoas...`
        : "Aguardando aproximação de usuário na portaria...";
    }
    const nome = ultimo.user || "Pessoa não identificada";
    const conf = ultimo.confidence ? `${(ultimo.confidence * 100).toFixed(1)}%` : "—";
    return `${nome} · match ${conf} · ${new Date(ultimo.data_hora as string).toLocaleTimeString("pt-BR")}`;
  };

  return (
    <>
      <div className="grid grid-cols-1 lg:grid-cols-[1.6fr_1fr] gap-3">
        <div className="bg-neutral-100/70 dark:bg-neutral-900/60 border border-neutral-200/80 dark:border-neutral-800 rounded-xl p-3 flex flex-col justify-between">
          <div>
            <div className="flex justify-between items-center mb-2">
              <div className="flex items-center gap-2">
                <span className="text-[13px] text-neutral-600 dark:text-neutral-400 font-medium">{cameraId}</span>

                <button
                  onClick={() => setModalConexao(true)}
                  className={`text-[10px] px-1.5 py-0.5 rounded flex items-center gap-1 border transition-colors ${
                    cameraInfo.conectado
                      ? "bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-400 border-emerald-300 dark:border-emerald-800"
                      : "bg-neutral-200/60 dark:bg-neutral-800 text-neutral-600 dark:text-neutral-400 border-neutral-300 dark:border-neutral-700 hover:bg-neutral-200"
                  }`}
                  title="Configurar endereço do ESP32-CAM"
                >
                  {cameraInfo.conectado ? (
                    <>
                      <IconWifi size={11} className="text-emerald-500" />
                      <span>{cameraInfo.fps > 0 ? `${cameraInfo.fps} FPS` : "Stream Ativo"}</span>
                    </>
                  ) : (
                    <>
                      <IconWifiOff size={11} />
                      <span>Conectar ESP32</span>
                    </>
                  )}
                </button>
              </div>

              <div className="flex items-center gap-1.5">
                <button
                  onClick={() => {
                    setFrameKey(Date.now());
                    setImgErro(false);
                    onRefresh();
                  }}
                  className="text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-200 transition-colors p-1"
                  title="Atualizar feed"
                  aria-label="Atualizar feed"
                >
                  <IconRefresh size={14} />
                </button>
                <StatusBadge status={aguardando ? "idle" : ultimo.status} variante="aovivo" tamanho="md" />
              </div>
            </div>

            <div className="relative aspect-[16/10] bg-neutral-200/60 dark:bg-neutral-950 rounded-lg overflow-hidden flex items-center justify-center border border-neutral-300/40 dark:border-neutral-800/80 shadow-inner">
              {!imgErro ? (
                // <img> de propósito: o quadro muda a cada 500 ms e vem do backend, então a
                // otimização/cache do next/image não se aplica.
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  key={frameKey}
                  src={`${API_BASE_URL}/api/camera/ultimo-frame?t=${frameKey}`}
                  alt="Feed da Câmera"
                  className="w-full h-full object-cover"
                  onError={() => setImgErro(true)}
                />
              ) : (
                <div className="flex flex-col items-center justify-center text-neutral-400 dark:text-neutral-500 gap-1.5">
                  <IconCamera size={36} stroke={1.5} />
                  <span className="text-xs">Câmera em espera</span>
                  {!cameraInfo.conectado && (
                    <button
                      onClick={() => setModalConexao(true)}
                      className="text-[11px] text-blue-600 dark:text-blue-400 hover:underline mt-1"
                    >
                      Conectar ao IP do ESP32-CAM
                    </button>
                  )}
                </div>
              )}

              <div className="absolute bottom-2 right-2 bg-black/60 backdrop-blur-xs text-[10px] text-white/90 px-2 py-0.5 rounded font-mono">
                {cameraInfo.conectado ? `ESP32-CAM · VGA · ${cameraInfo.fps} FPS` : "CAM-01 · ESP32-CAM"}
              </div>
            </div>
          </div>

          <p className="text-[13px] text-neutral-600 dark:text-neutral-400 mt-2 font-medium truncate">{legendaCamera()}</p>
        </div>

        <div className="bg-neutral-100/70 dark:bg-neutral-900/60 border border-neutral-200/80 dark:border-neutral-800 rounded-xl p-3 flex flex-col">
          <div className="flex items-center justify-between mb-2.5">
            <p className="text-[13px] text-neutral-600 dark:text-neutral-400 font-medium">Registro de entradas</p>
            <span className="text-[11px] text-neutral-400 dark:text-neutral-500">Tempo real (SSE)</span>
          </div>

          <div className="flex flex-col gap-2.5 overflow-y-auto max-h-[380px] pr-1">
            {logs.length === 0 ? (
              <div className="py-12 text-center text-xs text-neutral-400 dark:text-neutral-500">
                Nenhuma entrada registrada hoje.
              </div>
            ) : (
              logs.map((log) => (
                <div
                  key={log.id}
                  className="flex justify-between items-center py-1 border-b border-neutral-200/50 dark:border-neutral-800/50 last:border-0"
                >
                  <div className="flex items-start gap-2">
                    <span className={`w-2 h-2 rounded-full mt-1.5 shrink-0 ${COR_PONTO[infoStatus(log.status).tom]}`} />
                    <div>
                      <span className="text-[13px] text-neutral-800 dark:text-neutral-200 font-medium">
                        {log.usuario_nome || "Desconhecido"}
                      </span>
                      <p className="text-[12px] text-neutral-400 dark:text-neutral-500 -mt-0.5">
                        {formatarHora(log.data_hora)} · {formatarConfianca(log.confianca)}
                      </p>
                    </div>
                  </div>
                  <StatusBadge status={log.status} variante="aovivo" />
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {modalConexao && (
        <Modal
          titulo="Conexão com ESP32-CAM"
          descricao="Informe o endereço IP da sua placa ESP32-CAM conectada na mesma rede Wi-Fi. O servidor consumirá o stream contínuo e processará o reconhecimento facial automaticamente."
          onFechar={() => setModalConexao(false)}
          rodape={
            <div className="flex justify-between items-center">
              {cameraInfo.conectado ? (
                <button
                  type="button"
                  onClick={handleDesconectarCamera}
                  className="px-2.5 py-1 text-xs text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/40 rounded"
                >
                  Desconectar
                </button>
              ) : (
                <div />
              )}

              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setModalConexao(false)}
                  className="px-3 py-1.5 text-xs rounded-md text-neutral-600 dark:text-neutral-400 hover:bg-neutral-100 dark:hover:bg-neutral-800"
                >
                  Fechar
                </button>
                <button
                  type="button"
                  disabled={conectando || !urlEsp32.trim()}
                  onClick={handleConectarCamera}
                  className="px-3 py-1.5 text-xs font-medium rounded-md bg-neutral-900 text-white dark:bg-neutral-100 dark:text-neutral-900 hover:opacity-90 disabled:opacity-50"
                >
                  {conectando ? "Conectando..." : "Conectar Stream"}
                </button>
              </div>
            </div>
          }
        >
          <div>
            <label htmlFor="url-esp32" className="block text-xs font-medium text-neutral-700 dark:text-neutral-300 mb-1">
              Endereço IP / URL do ESP32-CAM
            </label>
            <input
              id="url-esp32"
              type="text"
              placeholder="Ex: http://192.168.0.55"
              value={urlEsp32}
              onChange={(e) => setUrlEsp32(e.target.value)}
              className="w-full text-xs px-2.5 py-2 rounded-md border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-800 text-neutral-900 dark:text-neutral-100 outline-none focus:ring-1 focus:ring-neutral-400 font-mono"
              autoFocus
            />
            <span className="text-[10px] text-neutral-400 mt-1 block">
              Dica: veja o IP exibido no Monitor Serial do Arduino IDE ao iniciar o ESP32.
            </span>
          </div>
          {erroConexao && (
            <p role="alert" className="text-xs text-rose-600 dark:text-rose-400">
              {erroConexao}
            </p>
          )}
        </Modal>
      )}
    </>
  );
}
