"use client";

import { useCallback, useEffect, useState } from "react";
import { Header } from "@/components/Header";
import { TabAoVivo } from "@/components/TabAoVivo";
import { TabButton } from "@/components/TabButton";
import { TabHistorico } from "@/components/TabHistorico";
import { TabPessoas } from "@/components/TabPessoas";
import {
  api,
  API_BASE_URL,
  CapturaDesconhecida,
  Estatisticas,
  LogAcesso,
  StatusSistema,
  Usuario,
} from "@/services/api";

type Aba = "vivo" | "pessoas" | "historico";

const ABAS: { id: Aba; rotulo: string }[] = [
  { id: "vivo", rotulo: "Ao vivo" },
  { id: "pessoas", rotulo: "Pessoas" },
  { id: "historico", rotulo: "Histórico" },
];

const INTERVALO_CONSULTA_MS = 8000;

export default function Home() {
  const [tabAtiva, setTabAtiva] = useState<Aba>("vivo");

  const [statusSistema, setStatusSistema] = useState<StatusSistema | null>(null);
  const [online, setOnline] = useState(false);
  const [logsRecentes, setLogsRecentes] = useState<LogAcesso[]>([]);
  const [excecoes, setExcecoes] = useState<LogAcesso[]>([]);
  const [usuarios, setUsuarios] = useState<Usuario[]>([]);
  const [capturas, setCapturas] = useState<CapturaDesconhecida[]>([]);
  const [estatisticas, setEstatisticas] = useState<Estatisticas | null>(null);
  // Muda quando chega um novo acesso; a aba Histórico recarrega a lista filtrada ao perceber.
  const [versaoDados, setVersaoDados] = useState(0);

  const carregarDados = useCallback(async () => {
    const [status, logs, exc, userList, capList, stats] = await Promise.all([
      api.getStatus().catch(() => null),
      api.getLogsRecentes(15).catch(() => []),
      api.getExcecoes(15).catch(() => []),
      api.getUsuarios().catch(() => []),
      api.getCapturasDesconhecidas().catch(() => []),
      api.getEstatisticas().catch(() => null),
    ]);

    setOnline(status !== null);
    if (status) setStatusSistema(status);
    setLogsRecentes(logs);
    setExcecoes(exc);
    setUsuarios(userList);
    setCapturas(capList);
    setEstatisticas(stats);
  }, []);

  const aoHaverNovosDados = useCallback(() => {
    setVersaoDados((v) => v + 1);
    carregarDados();
  }, [carregarDados]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- carga inicial vinda da API
    carregarDados();

    // Atualizações instantâneas por Server-Sent Events
    const eventSource = new EventSource(`${API_BASE_URL}/api/eventos`);
    eventSource.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.tipo === "novo_acesso" || payload.tipo === "treinamento_concluido") {
          aoHaverNovosDados();
        }
      } catch (e) {
        console.error("Erro ao processar evento SSE:", e);
      }
    };
    // Em caso de erro o navegador tenta reconectar sozinho.

    // Consulta periódica de segurança, caso algum evento se perca
    const intervalo = setInterval(carregarDados, INTERVALO_CONSULTA_MS);

    return () => {
      clearInterval(intervalo);
      eventSource.close();
    };
  }, [carregarDados, aoHaverNovosDados]);

  return (
    <main className="min-h-screen bg-neutral-50 dark:bg-neutral-950 text-neutral-900 dark:text-neutral-100 p-4 md:p-6 transition-colors">
      <div className="max-w-4xl mx-auto">
        <Header status={statusSistema} online={online} onSimulado={aoHaverNovosDados} />

        <div className="flex gap-2 mb-4" role="tablist">
          {ABAS.map((aba) => (
            <TabButton key={aba.id} ativa={tabAtiva === aba.id} onClick={() => setTabAtiva(aba.id)}>
              {aba.rotulo}
            </TabButton>
          ))}
        </div>

        {tabAtiva === "vivo" && <TabAoVivo statusSistema={statusSistema} logs={logsRecentes} onRefresh={carregarDados} />}
        {tabAtiva === "pessoas" && <TabPessoas usuarios={usuarios} capturas={capturas} onRefresh={carregarDados} />}
        {tabAtiva === "historico" && (
          <TabHistorico estatisticas={estatisticas} excecoes={excecoes} versaoDados={versaoDados} />
        )}

        <footer className="mt-8 pt-4 border-t border-neutral-200 dark:border-neutral-800 text-center text-xs text-neutral-400 dark:text-neutral-500">
          Trabalho de Conclusão de Curso · Sistema de Reconhecimento Facial de Baixo Custo com ESP32-CAM · IFSP Câmpus Birigui
        </footer>
      </div>
    </main>
  );
}
