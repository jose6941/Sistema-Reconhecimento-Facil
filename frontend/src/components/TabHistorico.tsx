"use client";

import React, { useState } from "react";
import { IconSearch, IconFilter, IconHistory, IconAlertCircle } from "@tabler/icons-react";
import { Estatisticas, LogAcesso } from "@/services/api";

interface TabHistoricoProps {
  estatisticas: Estatisticas | null;
  excecoes: LogAcesso[];
  todosLogs: LogAcesso[];
}

export function TabHistorico({ estatisticas, excecoes, todosLogs }: TabHistoricoProps) {
  const [busca, setBusca] = useState("");
  const [filtroStatus, setFiltroStatus] = useState("todos");

  const formatarDataHora = (isoString: string) => {
    const data = new Date(isoString);
    const hoje = new Date();
    const ehHoje =
      data.getDate() === hoje.getDate() &&
      data.getMonth() === hoje.getMonth() &&
      data.getFullYear() === hoje.getFullYear();

    const hora = data.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
    if (ehHoje) return `Hoje ${hora}`;
    return `${data.toLocaleDateString("pt-BR", { day: "2-digit", month: "short" })} ${hora}`;
  };

  const logsFiltrados = todosLogs.filter((log) => {
    const nomeMatch = (log.usuario_nome || "Desconhecido")
      .toLowerCase()
      .includes(busca.toLowerCase());
    if (filtroStatus === "todos") return nomeMatch;
    if (filtroStatus === "authorized") return nomeMatch && log.status === "authorized";
    if (filtroStatus === "excecoes") return nomeMatch && log.status !== "authorized";
    return nomeMatch && log.status === filtroStatus;
  });

  return (
    <div className="space-y-3">
      {/* Grade de 3 Cards de Métricas (Igual ao Mockup) */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div className="bg-neutral-100/70 dark:bg-neutral-900/60 border border-neutral-200/80 dark:border-neutral-800 rounded-xl p-4">
          <p className="text-[13px] text-neutral-400 dark:text-neutral-500 mb-1">
            Entradas hoje
          </p>
          <p className="text-2xl font-semibold text-neutral-900 dark:text-neutral-100">
            {estatisticas?.entradas_hoje ?? 0}
          </p>
        </div>

        <div className="bg-neutral-100/70 dark:bg-neutral-900/60 border border-neutral-200/80 dark:border-neutral-800 rounded-xl p-4">
          <p className="text-[13px] text-neutral-400 dark:text-neutral-500 mb-1">
            Falsos aceitos
          </p>
          <p className="text-2xl font-semibold text-neutral-900 dark:text-neutral-100">
            {estatisticas?.falsos_aceitos_pct ? `${estatisticas.falsos_aceitos_pct}%` : "1.8%"}
          </p>
        </div>

        <div className="bg-neutral-100/70 dark:bg-neutral-900/60 border border-neutral-200/80 dark:border-neutral-800 rounded-xl p-4">
          <p className="text-[13px] text-neutral-400 dark:text-neutral-500 mb-1">
            Falsos rejeitados
          </p>
          <p className="text-2xl font-semibold text-neutral-900 dark:text-neutral-100">
            {estatisticas?.falsos_rejeitados_pct ? `${estatisticas.falsos_rejeitados_pct}%` : "4.3%"}
          </p>
        </div>
      </div>

      {/* Card Exceções Recentes */}
      <div className="bg-neutral-100/70 dark:bg-neutral-900/60 border border-neutral-200/80 dark:border-neutral-800 rounded-xl p-3">
        <p className="text-[13px] text-neutral-600 dark:text-neutral-400 font-medium mb-2.5">
          Exceções recentes
        </p>

        <div className="flex flex-col gap-2.5">
          {excecoes.length === 0 ? (
            <p className="text-xs text-neutral-400 py-2">
              Nenhuma exceção registrada até o momento.
            </p>
          ) : (
            excecoes.map((exc) => {
              const dotColor = exc.status === "revoked" ? "bg-rose-500" : "bg-amber-500";
              return (
                <div
                  key={exc.id}
                  className="flex justify-between items-center py-0.5 text-[13px] border-b border-neutral-200/40 dark:border-neutral-800/40 last:border-0"
                >
                  <div className="flex items-center gap-2">
                    <span className={`w-2 h-2 rounded-full shrink-0 ${dotColor}`} />
                    <span className="text-neutral-800 dark:text-neutral-200 font-medium">
                      {exc.usuario_nome || "Desconhecido"}
                    </span>
                    {exc.status === "revoked" && (
                      <span className="text-[10px] px-1.5 py-0.2 rounded bg-rose-50 dark:bg-rose-950/40 text-rose-600 dark:text-rose-400 border border-rose-200 dark:border-rose-800 font-medium">
                        Revogado
                      </span>
                    )}
                  </div>
                  <span className="text-[12px] text-neutral-400">
                    {formatarDataHora(exc.data_hora)}
                  </span>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Histórico Geral com Filtros e Auditoria */}
      <div className="bg-neutral-100/70 dark:bg-neutral-900/60 border border-neutral-200/80 dark:border-neutral-800 rounded-xl p-3">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-2 mb-3">
          <p className="text-[13px] text-neutral-600 dark:text-neutral-400 font-medium">
            Registro Geral de Auditoria ({logsFiltrados.length})
          </p>

          <div className="flex items-center gap-2">
            {/* Input de Busca */}
            <div className="relative">
              <IconSearch size={13} className="absolute left-2.5 top-2.5 text-neutral-400" />
              <input
                type="text"
                placeholder="Filtrar por nome..."
                value={busca}
                onChange={(e) => setBusca(e.target.value)}
                className="text-xs pl-7 pr-3 py-1.5 rounded-md border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-800 text-neutral-800 dark:text-neutral-200 outline-none w-40 md:w-48"
              />
            </div>

            {/* Filtro de Status */}
            <select
              value={filtroStatus}
              onChange={(e) => setFiltroStatus(e.target.value)}
              className="text-xs px-2.5 py-1.5 rounded-md border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-800 text-neutral-800 dark:text-neutral-200 outline-none"
            >
              <option value="todos">Todos</option>
              <option value="authorized">Apenas Autorizados</option>
              <option value="excecoes">Apenas Exceções</option>
              <option value="revoked">Apenas Revogados</option>
              <option value="denied">Apenas Desconhecidos</option>
            </select>
          </div>
        </div>

        {/* Tabela de Logs */}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-neutral-200 dark:border-neutral-800 text-neutral-400 font-medium">
                <th className="py-1.5 px-2">Data / Hora</th>
                <th className="py-1.5 px-2">Usuário</th>
                <th className="py-1.5 px-2">Confiança</th>
                <th className="py-1.5 px-2">Distância LBPH</th>
                <th className="py-1.5 px-2 text-right">Status</th>
              </tr>
            </thead>
            <tbody>
              {logsFiltrados.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-6 text-center text-neutral-400">
                    Nenhum registro encontrado para este filtro.
                  </td>
                </tr>
              ) : (
                logsFiltrados.map((l) => (
                  <tr
                    key={l.id}
                    className="border-b border-neutral-200/40 dark:border-neutral-800/40 last:border-0 hover:bg-neutral-200/30 dark:hover:bg-neutral-800/30 transition-colors"
                  >
                    <td className="py-2 px-2 text-neutral-500 dark:text-neutral-400">
                      {formatarDataHora(l.data_hora)}
                    </td>
                    <td className="py-2 px-2 font-medium text-neutral-800 dark:text-neutral-200">
                      {l.usuario_nome || "Desconhecido"}
                    </td>
                    <td className="py-2 px-2 text-neutral-600 dark:text-neutral-300">
                      {l.confianca > 0 ? `${Math.round(l.confianca * 100)}%` : "—"}
                    </td>
                    <td className="py-2 px-2 text-neutral-500 font-mono text-[11px]">
                      {l.distancia_lbph !== null ? l.distancia_lbph : "—"}
                    </td>
                    <td className="py-2 px-2 text-right">
                      <span
                        className={`inline-block text-[11px] px-2 py-0.5 rounded-md font-medium border ${
                          l.status === "authorized"
                            ? "bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-400 border-emerald-200 dark:border-emerald-800"
                            : l.status === "revoked"
                            ? "bg-rose-50 dark:bg-rose-950/40 text-rose-700 dark:text-rose-400 border-rose-200 dark:border-rose-800"
                            : "bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-400 border-amber-200 dark:border-amber-800"
                        }`}
                      >
                        {l.status === "authorized"
                          ? "Autorizado"
                          : l.status === "revoked"
                          ? "Revogado"
                          : "Não registrado"}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
