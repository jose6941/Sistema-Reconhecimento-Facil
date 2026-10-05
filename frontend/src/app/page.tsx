"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Header } from "@/components/Header";
import { TabAoVivo } from "@/components/TabAoVivo";
import { TabPessoas } from "@/components/TabPessoas";
import { TabHistorico } from "@/components/TabHistorico";
import {
  api,
  API_BASE_URL,
  StatusSistema,
  LogAcesso,
  Usuario,
  CapturaDesconhecida,
  Estatisticas,
} from "@/services/api";

export default function Home() {
  const [tabAtiva, setTabAtiva] = useState<"vivo" | "pessoas" | "historico">("vivo");

  // Estados dos Dados
  const [statusSistema, setStatusSistema] = useState<StatusSistema | null>(null);
  const [online, setOnline] = useState(false);
  const [logsRecentes, setLogsRecentes] = useState<LogAcesso[]>([]);
  const [todosLogs, setTodosLogs] = useState<LogAcesso[]>([]);
  const [excecoes, setExcecoes] = useState<LogAcesso[]>([]);
  const [usuarios, setUsuarios] = useState<Usuario[]>([]);
  const [capturas, setCapturas] = useState<CapturaDesconhecida[]>([]);
  const [estatisticas, setEstatisticas] = useState<Estatisticas | null>(null);

  // Carrega todos os dados do Backend
  const carregarDados = useCallback(async () => {
    try {
      const [status, logs, exc, userList, capList, stats, todos] = await Promise.all([
        api.getStatus().catch(() => null),
        api.getLogsRecentes(15).catch(() => []),
        api.getExcecoes(15).catch(() => []),
        api.getUsuarios().catch(() => []),
        api.getCapturasDesconhecidas().catch(() => []),
        api.getEstatisticas().catch(() => null),
        api.getLogs({ limite: 100 }).catch(() => []),
      ]);

      if (status) {
        setStatusSistema(status);
        setOnline(true);
      } else {
        setOnline(false);
      }

      setLogsRecentes(logs);
      setExcecoes(exc);
      setUsuarios(userList);
      setCapturas(capList);
      setEstatisticas(stats);
      setTodosLogs(todos);
    } catch {
      setOnline(false);
    }
  }, []);

  // Efeito inicial e conexão Server-Sent Events (SSE)
  useEffect(() => {
    carregarDados();

    // Conexão SSE para atualizações em tempo real instantâneas
    let eventSource: EventSource | null = null;
    try {
      eventSource = new EventSource(`${API_BASE_URL}/api/eventos`);

      eventSource.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          if (payload.tipo === "novo_acesso") {
            // Atualiza logs e status imediatamente
            carregarDados();
          } else if (payload.tipo === "treinamento_concluido") {
            carregarDados();
          }
        } catch (e) {
          console.error("Erro ao processar evento SSE:", e);
        }
      };

      eventSource.onerror = () => {
        // SSE tentará reconectar automaticamente
      };
    } catch (e) {
      console.error("Falha ao abrir EventSource:", e);
    }

    // Polling de segurança a cada 8 segundos
    const interval = setInterval(carregarDados, 8000);

    return () => {
      clearInterval(interval);
      if (eventSource) eventSource.close();
    };
  }, [carregarDados]);

  return (
    <main className="min-h-screen bg-neutral-50 dark:bg-neutral-950 text-neutral-900 dark:text-neutral-100 p-4 md:p-6 transition-colors">
      <div className="max-w-4xl mx-auto">
        {/* Cabeçalho */}
        <Header status={statusSistema} online={online} onSimulado={carregarDados} />

        {/* Navegação por Abas (Estilo do Mockup) */}
        <div className="flex gap-2 mb-4">
          <button
            onClick={() => setTabAtiva("vivo")}
            className={`flex-1 py-2 px-3 text-xs md:text-[13px] font-medium rounded-lg border transition-all cursor-pointer ${
              tabAtiva === "vivo"
                ? "bg-white dark:bg-neutral-900 text-neutral-900 dark:text-neutral-100 border-neutral-300 dark:border-neutral-700 shadow-2xs"
                : "bg-neutral-100 dark:bg-neutral-800/60 text-neutral-600 dark:text-neutral-400 border-transparent hover:bg-neutral-200/60 dark:hover:bg-neutral-800"
            }`}
          >
            Ao vivo
          </button>

          <button
            onClick={() => setTabAtiva("pessoas")}
            className={`flex-1 py-2 px-3 text-xs md:text-[13px] font-medium rounded-lg border transition-all cursor-pointer ${
              tabAtiva === "pessoas"
                ? "bg-white dark:bg-neutral-900 text-neutral-900 dark:text-neutral-100 border-neutral-300 dark:border-neutral-700 shadow-2xs"
                : "bg-neutral-100 dark:bg-neutral-800/60 text-neutral-600 dark:text-neutral-400 border-transparent hover:bg-neutral-200/60 dark:hover:bg-neutral-800"
            }`}
          >
            Pessoas
          </button>

          <button
            onClick={() => setTabAtiva("historico")}
            className={`flex-1 py-2 px-3 text-xs md:text-[13px] font-medium rounded-lg border transition-all cursor-pointer ${
              tabAtiva === "historico"
                ? "bg-white dark:bg-neutral-900 text-neutral-900 dark:text-neutral-100 border-neutral-300 dark:border-neutral-700 shadow-2xs"
                : "bg-neutral-100 dark:bg-neutral-800/60 text-neutral-600 dark:text-neutral-400 border-transparent hover:bg-neutral-200/60 dark:hover:bg-neutral-800"
            }`}
          >
            Histórico
          </button>
        </div>

        {/* Telas das Abas */}
        {tabAtiva === "vivo" && (
          <TabAoVivo
            statusSistema={statusSistema}
            logs={logsRecentes}
            onRefresh={carregarDados}
          />
        )}

        {tabAtiva === "pessoas" && (
          <TabPessoas
            usuarios={usuarios}
            capturas={capturas}
            onRefresh={carregarDados}
          />
        )}

        {tabAtiva === "historico" && (
          <TabHistorico
            estatisticas={estatisticas}
            excecoes={excecoes}
            todosLogs={todosLogs}
          />
        )}

        {/* Rodapé Acadêmico do TCC */}
        <footer className="mt-8 pt-4 border-t border-neutral-200 dark:border-neutral-800 text-center text-xs text-neutral-400 dark:text-neutral-500">
          Trabalho de Conclusão de Curso · Sistema de Reconhecimento Facial de Baixo Custo com ESP32-CAM · IFSP Câmpus Birigui
        </footer>
      </div>
    </main>
  );
}
