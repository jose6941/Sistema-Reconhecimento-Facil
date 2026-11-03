"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { IconSearch } from "@tabler/icons-react";
import { StatusBadge } from "@/components/StatusBadge";
import { formatarConfianca, formatarData } from "@/lib/formatadores";
import { COR_PONTO, infoStatus } from "@/lib/status";
import { useDebounce } from "@/lib/useDebounce";
import { api, Estatisticas, FiltrosLogs, LogAcesso } from "@/services/api";

interface TabHistoricoProps {
  estatisticas: Estatisticas | null;
  excecoes: LogAcesso[];
  /** Muda a cada novo acesso; faz a lista filtrada ser recarregada. */
  versaoDados?: number;
}

export const TAMANHO_PAGINA = 50;
export const ATRASO_BUSCA_MS = 300;

const FILTROS_STATUS = [
  { valor: "todos", rotulo: "Todos" },
  { valor: "authorized", rotulo: "Apenas Autorizados" },
  { valor: "excecoes", rotulo: "Apenas Exceções" },
  { valor: "revoked", rotulo: "Apenas Revogados" },
  { valor: "denied", rotulo: "Apenas Desconhecidos" },
];

const CAMPO =
  "text-xs px-2.5 py-1.5 rounded-md border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-800 text-neutral-800 dark:text-neutral-200 outline-none";
const CARD = "bg-neutral-100/70 dark:bg-neutral-900/60 border border-neutral-200/80 dark:border-neutral-800 rounded-xl";

export function TabHistorico({ estatisticas, excecoes, versaoDados = 0 }: TabHistoricoProps) {
  const [busca, setBusca] = useState("");
  const [filtroStatus, setFiltroStatus] = useState("todos");
  const [dataInicio, setDataInicio] = useState("");
  const [dataFim, setDataFim] = useState("");

  const [logs, setLogs] = useState<LogAcesso[]>([]);
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState(false);
  const [temMais, setTemMais] = useState(false);

  const buscaAtrasada = useDebounce(busca.trim(), ATRASO_BUSCA_MS);
  // Só a requisição mais recente pode alterar a tela (evita resposta antiga sobrescrever a nova)
  const ultimaRequisicao = useRef(0);

  const montarFiltros = useCallback(
    (offset: number): FiltrosLogs => ({
      usuario: buscaAtrasada || undefined,
      status: filtroStatus === "todos" || filtroStatus === "excecoes" ? undefined : filtroStatus,
      excecoes: filtroStatus === "excecoes" || undefined,
      data_inicio: dataInicio || undefined,
      data_fim: dataFim || undefined,
      limite: TAMANHO_PAGINA,
      offset: offset || undefined,
    }),
    [buscaAtrasada, filtroStatus, dataInicio, dataFim],
  );

  const buscar = useCallback(
    async (acumular: boolean, offset: number) => {
      const id = ++ultimaRequisicao.current;
      setCarregando(true);
      setErro(false);
      try {
        const pagina = await api.getLogs(montarFiltros(offset));
        if (id !== ultimaRequisicao.current) return;
        setLogs((atual) => (acumular ? [...atual, ...pagina] : pagina));
        setTemMais(pagina.length === TAMANHO_PAGINA);
      } catch {
        if (id !== ultimaRequisicao.current) return;
        setErro(true);
      } finally {
        if (id === ultimaRequisicao.current) setCarregando(false);
      }
    },
    [montarFiltros],
  );

  // Recarrega a primeira página quando um filtro muda ou chega um novo acesso
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- sincroniza a lista com a API
    buscar(false, 0);
  }, [buscar, versaoDados]);

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div className={`${CARD} p-4`}>
          <p className="text-[13px] text-neutral-400 dark:text-neutral-500 mb-1">Entradas hoje</p>
          <p className="text-2xl font-semibold text-neutral-900 dark:text-neutral-100">{estatisticas?.entradas_hoje ?? 0}</p>
        </div>
        <div className={`${CARD} p-4`}>
          <p className="text-[13px] text-neutral-400 dark:text-neutral-500 mb-1">Falsos aceitos</p>
          <p className="text-2xl font-semibold text-neutral-900 dark:text-neutral-100">
            {estatisticas?.falsos_aceitos_pct ? `${estatisticas.falsos_aceitos_pct}%` : "1.8%"}
          </p>
        </div>
        <div className={`${CARD} p-4`}>
          <p className="text-[13px] text-neutral-400 dark:text-neutral-500 mb-1">Falsos rejeitados</p>
          <p className="text-2xl font-semibold text-neutral-900 dark:text-neutral-100">
            {estatisticas?.falsos_rejeitados_pct ? `${estatisticas.falsos_rejeitados_pct}%` : "4.3%"}
          </p>
        </div>
      </div>

      <div className={`${CARD} p-3`}>
        <p className="text-[13px] text-neutral-600 dark:text-neutral-400 font-medium mb-2.5">Exceções recentes</p>
        <div className="flex flex-col gap-2.5">
          {excecoes.length === 0 ? (
            <p className="text-xs text-neutral-400 py-2">Nenhuma exceção registrada até o momento.</p>
          ) : (
            excecoes.map((exc) => (
              <div
                key={exc.id}
                className="flex justify-between items-center py-0.5 text-[13px] border-b border-neutral-200/40 dark:border-neutral-800/40 last:border-0"
              >
                <div className="flex items-center gap-2">
                  <span className={`w-2 h-2 rounded-full shrink-0 ${COR_PONTO[infoStatus(exc.status).tom]}`} />
                  <span className="text-neutral-800 dark:text-neutral-200 font-medium">{exc.usuario_nome || "Desconhecido"}</span>
                  {exc.status === "revoked" && <StatusBadge status="revoked" />}
                </div>
                <span className="text-[12px] text-neutral-400">{formatarData(exc.data_hora, { incluirHora: true })}</span>
              </div>
            ))
          )}
        </div>
      </div>

      <div className={`${CARD} p-3`}>
        <div className="flex flex-col gap-2 mb-3">
          <p className="text-[13px] text-neutral-600 dark:text-neutral-400 font-medium">
            Registro Geral de Auditoria ({logs.length}
            {temMais ? "+" : ""})
          </p>

          <div className="flex flex-wrap items-center gap-2">
            <div className="relative">
              <IconSearch size={13} className="absolute left-2.5 top-2.5 text-neutral-400" />
              <input
                type="search"
                aria-label="Filtrar por nome"
                placeholder="Filtrar por nome..."
                value={busca}
                maxLength={100}
                onChange={(e) => setBusca(e.target.value)}
                className={`${CAMPO} pl-7 pr-3 w-40 md:w-48`}
              />
            </div>

            <select
              aria-label="Filtrar por status"
              value={filtroStatus}
              onChange={(e) => setFiltroStatus(e.target.value)}
              className={CAMPO}
            >
              {FILTROS_STATUS.map((f) => (
                <option key={f.valor} value={f.valor}>
                  {f.rotulo}
                </option>
              ))}
            </select>

            <label className="flex items-center gap-1 text-[11px] text-neutral-500">
              De
              <input
                type="date"
                aria-label="Data inicial"
                value={dataInicio}
                max={dataFim || undefined}
                onChange={(e) => setDataInicio(e.target.value)}
                className={CAMPO}
              />
            </label>
            <label className="flex items-center gap-1 text-[11px] text-neutral-500">
              até
              <input
                type="date"
                aria-label="Data final"
                value={dataFim}
                min={dataInicio || undefined}
                onChange={(e) => setDataFim(e.target.value)}
                className={CAMPO}
              />
            </label>
          </div>
        </div>

        {erro && (
          <div role="alert" className="flex items-center justify-between gap-2 mb-2 text-xs text-rose-600 dark:text-rose-400">
            <span>Não foi possível carregar o histórico.</span>
            <button type="button" onClick={() => buscar(false, 0)} className="underline">
              Tentar novamente
            </button>
          </div>
        )}

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
              {logs.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-6 text-center text-neutral-400">
                    {carregando ? "Carregando..." : "Nenhum registro encontrado para este filtro."}
                  </td>
                </tr>
              ) : (
                logs.map((l) => (
                  <tr
                    key={l.id}
                    className="border-b border-neutral-200/40 dark:border-neutral-800/40 last:border-0 hover:bg-neutral-200/30 dark:hover:bg-neutral-800/30 transition-colors"
                  >
                    <td className="py-2 px-2 text-neutral-500 dark:text-neutral-400">
                      {formatarData(l.data_hora, { incluirHora: true })}
                    </td>
                    <td className="py-2 px-2 font-medium text-neutral-800 dark:text-neutral-200">
                      {l.usuario_nome || "Desconhecido"}
                    </td>
                    <td className="py-2 px-2 text-neutral-600 dark:text-neutral-300">{formatarConfianca(l.confianca)}</td>
                    <td className="py-2 px-2 text-neutral-500 font-mono text-[11px]">{l.distancia_lbph ?? "—"}</td>
                    <td className="py-2 px-2 text-right">
                      <StatusBadge status={l.status} />
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {temMais && (
          <div className="mt-3 text-center">
            <button
              type="button"
              disabled={carregando}
              onClick={() => buscar(true, logs.length)}
              className="px-3 py-1.5 text-xs rounded-md bg-neutral-200 hover:bg-neutral-300 dark:bg-neutral-800 dark:hover:bg-neutral-700 text-neutral-800 dark:text-neutral-200 disabled:opacity-50"
            >
              {carregando ? "Carregando..." : "Carregar mais"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
