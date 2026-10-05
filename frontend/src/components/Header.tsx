"use client";

import React, { useState } from "react";
import { IconCpu, IconCamera, IconPlayerPlay, IconCheck, IconX, IconAlertTriangle } from "@tabler/icons-react";
import { StatusSistema, api } from "@/services/api";

interface HeaderProps {
  status: StatusSistema | null;
  online: boolean;
  onSimulado: () => void;
}

export function Header({ status, online, onSimulado }: HeaderProps) {
  const [modalSimular, setModalSimular] = useState(false);
  const [simulando, setSimulando] = useState(false);
  const [nomeSimulado, setNomeSimulado] = useState("Marina Costa");
  const [tipoSimulado, setTipoSimulado] = useState<"autorizado" | "negado" | "revogado">("autorizado");

  const executarSimulacao = async () => {
    setSimulando(true);
    try {
      await api.simularLeitura(tipoSimulado, nomeSimulado);
      onSimulado();
      setModalSimular(false);
    } catch (e) {
      console.error("Erro ao simular:", e);
    } finally {
      setSimulando(false);
    }
  };

  return (
    <>
      <header className="flex flex-col md:flex-row items-start md:items-center justify-between gap-3 pb-4 mb-4 border-b border-neutral-200 dark:border-neutral-800">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-base md:text-lg font-semibold tracking-tight text-neutral-900 dark:text-neutral-100">
              Sistema de Reconhecimento Facial
            </h1>
            <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-neutral-100 dark:bg-neutral-800 text-neutral-600 dark:text-neutral-300 border border-neutral-200 dark:border-neutral-700">
              ESP32-CAM · TCC IFSP
            </span>
          </div>
          <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-0.5">
            Processamento em borda com OpenCV & Classificador LBPH
          </p>
        </div>

        <div className="flex items-center flex-wrap gap-2 text-xs">
          {/* Status do Servidor */}
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-neutral-100 dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700 text-neutral-700 dark:text-neutral-300">
            <span
              className={`w-2 h-2 rounded-full ${online ? "bg-emerald-500 animate-pulse" : "bg-rose-500"}`}
            />
            <span>{online ? "Servidor Ativo" : "Desconectado"}</span>
          </div>

          {/* Status do Modelo LBPH */}
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-neutral-100 dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700 text-neutral-700 dark:text-neutral-300">
            <IconCpu size={14} className="text-neutral-500" />
            <span>
              {status?.modelo_carregado
                ? `LBPH: ${status.total_identidades} pessoas`
                : "Modelo não treinado"}
            </span>
          </div>

          {/* Botão de Simulação (Ideal para apresentação de TCC) */}
          <button
            onClick={() => setModalSimular(true)}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-neutral-900 hover:bg-neutral-800 dark:bg-neutral-100 dark:hover:bg-neutral-200 text-white dark:text-neutral-900 font-medium transition-all"
            title="Simular leitura de acesso para demonstração na banca"
          >
            <IconPlayerPlay size={13} />
            <span>Simular Leitura</span>
          </button>
        </div>
      </header>

      {/* Modal de Simulação para Demonstração */}
      {modalSimular && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-xs p-4">
          <div className="bg-white dark:bg-neutral-900 rounded-xl border border-neutral-200 dark:border-neutral-800 max-w-sm w-full p-5 shadow-xl">
            <h3 className="text-sm font-semibold text-neutral-900 dark:text-neutral-100 mb-1">
              Simular Leitura da Portaria
            </h3>
            <p className="text-xs text-neutral-500 dark:text-neutral-400 mb-4">
              Dispare um evento em tempo real para demonstrar o comportamento do sistema sem precisar do ESP32-CAM.
            </p>

            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-neutral-700 dark:text-neutral-300 mb-1">
                  Tipo de Resultado
                </label>
                <div className="grid grid-cols-3 gap-1.5">
                  <button
                    type="button"
                    onClick={() => {
                      setTipoSimulado("autorizado");
                      setNomeSimulado("Marina Costa");
                    }}
                    className={`py-1.5 text-xs font-medium rounded-md border flex items-center justify-center gap-1 ${
                      tipoSimulado === "autorizado"
                        ? "bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-400 border-emerald-300 dark:border-emerald-800"
                        : "border-neutral-200 dark:border-neutral-700 text-neutral-600 dark:text-neutral-400"
                    }`}
                  >
                    <IconCheck size={12} /> Autorizado
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setTipoSimulado("revogado");
                      setNomeSimulado("Sérgio Baptista");
                    }}
                    className={`py-1.5 text-xs font-medium rounded-md border flex items-center justify-center gap-1 ${
                      tipoSimulado === "revogado"
                        ? "bg-rose-50 dark:bg-rose-950/40 text-rose-700 dark:text-rose-400 border-rose-300 dark:border-rose-800"
                        : "border-neutral-200 dark:border-neutral-700 text-neutral-600 dark:text-neutral-400"
                    }`}
                  >
                    <IconX size={12} /> Revogado
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setTipoSimulado("negado");
                      setNomeSimulado("Desconhecido");
                    }}
                    className={`py-1.5 text-xs font-medium rounded-md border flex items-center justify-center gap-1 ${
                      tipoSimulado === "negado"
                        ? "bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-400 border-amber-300 dark:border-amber-800"
                        : "border-neutral-200 dark:border-neutral-700 text-neutral-600 dark:text-neutral-400"
                    }`}
                  >
                    <IconAlertTriangle size={12} /> Desconhecido
                  </button>
                </div>
              </div>

              {tipoSimulado !== "negado" && (
                <div>
                  <label className="block text-xs font-medium text-neutral-700 dark:text-neutral-300 mb-1">
                    Nome da Pessoa
                  </label>
                  <input
                    type="text"
                    value={nomeSimulado}
                    onChange={(e) => setNomeSimulado(e.target.value)}
                    className="w-full text-xs px-2.5 py-1.5 rounded-md border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-800 text-neutral-900 dark:text-neutral-100 outline-none focus:ring-1 focus:ring-neutral-400"
                  />
                </div>
              )}
            </div>

            <div className="flex justify-end gap-2 mt-5">
              <button
                type="button"
                onClick={() => setModalSimular(false)}
                className="px-3 py-1.5 text-xs rounded-md text-neutral-600 dark:text-neutral-400 hover:bg-neutral-100 dark:hover:bg-neutral-800"
              >
                Cancelar
              </button>
              <button
                type="button"
                disabled={simulando}
                onClick={executarSimulacao}
                className="px-3 py-1.5 text-xs font-medium rounded-md bg-neutral-900 text-white dark:bg-neutral-100 dark:text-neutral-900 hover:opacity-90 disabled:opacity-50"
              >
                {simulando ? "Disparando..." : "Disparar Leitura"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
