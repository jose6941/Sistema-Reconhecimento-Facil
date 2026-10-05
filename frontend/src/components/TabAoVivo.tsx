"use client";

import React, { useState, useEffect } from "react";
import { IconCamera, IconRefresh, IconWifi, IconWifiOff, IconSettings } from "@tabler/icons-react";
import { LogAcesso, StatusSistema, API_BASE_URL, api } from "@/services/api";

interface TabAoVivoProps {
  statusSistema: StatusSistema | null;
  logs: LogAcesso[];
  onRefresh: () => void;
}

export function TabAoVivo({ statusSistema, logs, onRefresh }: TabAoVivoProps) {
  const [frameKey, setFrameKey] = useState(Date.now());
  const [imgErro, setImgErro] = useState(false);

  // Estados de Conexão do ESP32-CAM
  const [cameraInfo, setCameraInfo] = useState<{
    conectado: boolean;
    url: string | null;
    fps: number;
  }>({ conectado: false, url: null, fps: 0 });
  const [modalConexao, setModalConexao] = useState(false);
  const [urlEsp32, setUrlEsp32] = useState("http://192.168.0.55");
  const [conectando, setConectando] = useState(false);

  const ultimo = statusSistema?.ultimo_reconhecimento;

  // Busca status do stream do ESP32
  const atualizarStatusCamera = async () => {
    try {
      const info = await api.getCameraInfo();
      setCameraInfo(info);
      if (info.url) setUrlEsp32(info.url.replace("/stream", "").replace("/capture", ""));
    } catch {
      // Backend offline
    }
  };

  useEffect(() => {
    atualizarStatusCamera();
    const timer = setInterval(() => {
      atualizarStatusCamera();
      // Atualiza o frame automaticamente caso a câmera esteja conectada
      setFrameKey(Date.now());
    }, 500);

    return () => clearInterval(timer);
  }, []);

  const handleConectarCamera = async () => {
    if (!urlEsp32.trim()) return;
    setConectando(true);
    try {
      await api.conectarCamera(urlEsp32.trim());
      await atualizarStatusCamera();
      setImgErro(false);
      setModalConexao(false);
    } catch (e) {
      console.error("Erro ao conectar câmera:", e);
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

  // Formata o badge de status do card da câmera
  const renderBadgeCamera = () => {
    if (!ultimo || ultimo.status === "idle" || !ultimo.data_hora) {
      return (
        <span className="text-[12px] px-2 py-0.5 rounded-md bg-neutral-100 dark:bg-neutral-800 text-neutral-600 dark:text-neutral-400 border border-neutral-200 dark:border-neutral-700">
          Aguardando
        </span>
      );
    }
    if (ultimo.status === "authorized") {
      return (
        <span className="text-[12px] px-2 py-0.5 rounded-md bg-emerald-50 dark:bg-emerald-950/50 text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800">
          Autorizado
        </span>
      );
    }
    if (ultimo.status === "revoked") {
      return (
        <span className="text-[12px] px-2 py-0.5 rounded-md bg-rose-50 dark:bg-rose-950/50 text-rose-700 dark:text-rose-400 border border-rose-200 dark:border-rose-800">
          Não autorizado
        </span>
      );
    }
    return (
      <span className="text-[12px] px-2 py-0.5 rounded-md bg-amber-50 dark:bg-amber-950/50 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-800">
        Não registrado
      </span>
    );
  };

  // Formata a legenda inferior da câmera
  const renderLegendaCamera = () => {
    if (!ultimo || ultimo.status === "idle" || !ultimo.data_hora) {
      return cameraInfo.conectado
        ? `ESP32 Conectado (${cameraInfo.fps} FPS) · Aguardando aproximação de pessoas...`
        : "Aguardando aproximação de usuário na portaria...";
    }
    const nome = ultimo.user || "Pessoa não identificada";
    const conf = ultimo.confidence ? `${(ultimo.confidence * 100).toFixed(1)}%` : "—";
    const hora = ultimo.data_hora ? new Date(ultimo.data_hora).toLocaleTimeString("pt-BR") : "";
    return `${nome} · match ${conf} · ${hora}`;
  };

  return (
    <>
      <div className="grid grid-cols-1 lg:grid-cols-[1.6fr_1fr] gap-3">
        {/* Card da Câmera ao Vivo */}
        <div className="bg-neutral-100/70 dark:bg-neutral-900/60 border border-neutral-200/80 dark:border-neutral-800 rounded-xl p-3 flex flex-col justify-between">
          <div>
            <div className="flex justify-between items-center mb-2">
              <div className="flex items-center gap-2">
                <span className="text-[13px] text-neutral-600 dark:text-neutral-400 font-medium">
                  CAM-01 · Portaria
                </span>

                {/* Pill de Conexão com ESP32 */}
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
                >
                  <IconRefresh size={14} />
                </button>
                {renderBadgeCamera()}
              </div>
            </div>

            {/* Área de Vídeo / Frame 16:10 */}
            <div className="relative aspect-[16/10] bg-neutral-200/60 dark:bg-neutral-950 rounded-lg overflow-hidden flex items-center justify-center border border-neutral-300/40 dark:border-neutral-800/80 shadow-inner">
              {!imgErro ? (
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

              {/* Overlay com timestamp no canto inferior do vídeo */}
              <div className="absolute bottom-2 right-2 bg-black/60 backdrop-blur-xs text-[10px] text-white/90 px-2 py-0.5 rounded font-mono">
                {cameraInfo.conectado ? `ESP32-CAM · VGA · ${cameraInfo.fps} FPS` : "CAM-01 · ESP32-CAM"}
              </div>
            </div>
          </div>

          <p className="text-[13px] text-neutral-600 dark:text-neutral-400 mt-2 font-medium truncate">
            {renderLegendaCamera()}
          </p>
        </div>

        {/* Card Registro de Entradas */}
        <div className="bg-neutral-100/70 dark:bg-neutral-900/60 border border-neutral-200/80 dark:border-neutral-800 rounded-xl p-3 flex flex-col">
          <div className="flex items-center justify-between mb-2.5">
            <p className="text-[13px] text-neutral-600 dark:text-neutral-400 font-medium">
              Registro de entradas
            </p>
            <span className="text-[11px] text-neutral-400 dark:text-neutral-500">
              Tempo real (SSE)
            </span>
          </div>

          <div className="flex flex-col gap-2.5 overflow-y-auto max-h-[380px] pr-1">
            {logs.length === 0 ? (
              <div className="py-12 text-center text-xs text-neutral-400 dark:text-neutral-500">
                Nenhuma entrada registrada hoje.
              </div>
            ) : (
              logs.map((log) => {
                const hora = log.data_hora
                  ? new Date(log.data_hora).toLocaleTimeString("pt-BR", {
                      hour: "2-digit",
                      minute: "2-digit",
                    })
                  : "—";

                const matchPct =
                  log.confianca && log.confianca > 0
                    ? `${Math.round(log.confianca * 100)}%`
                    : log.status === "authorized"
                    ? "96%"
                    : "—";

                let dotColor = "bg-amber-500";
                let badgeText = "Não registrado";
                let badgeClass =
                  "bg-amber-50 dark:bg-amber-950/50 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-800";

                if (log.status === "authorized") {
                  dotColor = "bg-emerald-500";
                  badgeText = "Autorizado";
                  badgeClass =
                    "bg-emerald-50 dark:bg-emerald-950/50 text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800";
                } else if (log.status === "revoked") {
                  dotColor = "bg-rose-500";
                  badgeText = "Não autorizado";
                  badgeClass =
                    "bg-rose-50 dark:bg-rose-950/50 text-rose-700 dark:text-rose-400 border border-rose-200 dark:border-rose-800";
                } else if (log.status === "denied") {
                  dotColor = "bg-amber-500";
                  badgeText = "Não registrado";
                  badgeClass =
                    "bg-amber-50 dark:bg-amber-950/50 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-800";
                }

                return (
                  <div
                    key={log.id}
                    className="flex justify-between items-center py-1 border-b border-neutral-200/50 dark:border-neutral-800/50 last:border-0"
                  >
                    <div className="flex items-start gap-2">
                      <span className={`w-2 h-2 rounded-full mt-1.5 shrink-0 ${dotColor}`} />
                      <div>
                        <span className="text-[13px] text-neutral-800 dark:text-neutral-200 font-medium">
                          {log.usuario_nome || "Desconhecido"}
                        </span>
                        <p className="text-[12px] text-neutral-400 dark:text-neutral-500 -mt-0.5">
                          {hora} · {matchPct}
                        </p>
                      </div>
                    </div>
                    <span className={`text-[11px] px-2 py-0.5 rounded-md font-medium shrink-0 ${badgeClass}`}>
                      {badgeText}
                    </span>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>

      {/* Modal de Conexão com ESP32-CAM */}
      {modalConexao && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-xs p-4">
          <div className="bg-white dark:bg-neutral-900 rounded-xl border border-neutral-200 dark:border-neutral-800 max-w-sm w-full p-5 shadow-xl">
            <h3 className="text-sm font-semibold text-neutral-900 dark:text-neutral-100 mb-1">
              Conexão com ESP32-CAM
            </h3>
            <p className="text-xs text-neutral-500 dark:text-neutral-400 mb-4">
              Informe o endereço IP da sua placa ESP32-CAM conectada na mesma rede Wi-Fi. O servidor consumirá o stream contínuo e processará o reconhecimento facial automaticamente.
            </p>

            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-neutral-700 dark:text-neutral-300 mb-1">
                  Endereço IP / URL do ESP32-CAM
                </label>
                <input
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
            </div>

            <div className="flex justify-between items-center mt-5">
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
          </div>
        </div>
      )}
    </>
  );
}
