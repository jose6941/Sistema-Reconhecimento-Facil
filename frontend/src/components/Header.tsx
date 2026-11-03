"use client";

import Link from "next/link";
import { useState } from "react";
import { IconAlertTriangle, IconBook, IconCheck, IconCpu, IconPlayerPlay, IconX } from "@tabler/icons-react";
import { Modal } from "@/components/Modal";
import { api, StatusSistema } from "@/services/api";

interface HeaderProps {
  status: StatusSistema | null;
  online: boolean;
  onSimulado: () => void;
}

type TipoSimulado = "autorizado" | "negado" | "revogado";

const OPCOES_SIMULACAO: {
  tipo: TipoSimulado;
  rotulo: string;
  nomePadrao: string;
  Icone: typeof IconCheck;
  classeAtiva: string;
}[] = [
  {
    tipo: "autorizado",
    rotulo: "Autorizado",
    nomePadrao: "Marina Costa",
    Icone: IconCheck,
    classeAtiva:
      "bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-400 border-emerald-300 dark:border-emerald-800",
  },
  {
    tipo: "revogado",
    rotulo: "Revogado",
    nomePadrao: "Sérgio Baptista",
    Icone: IconX,
    classeAtiva: "bg-rose-50 dark:bg-rose-950/40 text-rose-700 dark:text-rose-400 border-rose-300 dark:border-rose-800",
  },
  {
    tipo: "negado",
    rotulo: "Desconhecido",
    nomePadrao: "Desconhecido",
    Icone: IconAlertTriangle,
    classeAtiva:
      "bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-400 border-amber-300 dark:border-amber-800",
  },
];

const BOTAO_CHIP =
  "flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-neutral-100 dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700 text-neutral-700 dark:text-neutral-300";

export function Header({ status, online, onSimulado }: HeaderProps) {
  const [modalSimular, setModalSimular] = useState(false);
  const [simulando, setSimulando] = useState(false);
  const [nomeSimulado, setNomeSimulado] = useState("Marina Costa");
  const [tipoSimulado, setTipoSimulado] = useState<TipoSimulado>("autorizado");
  const [erro, setErro] = useState<string | null>(null);

  const executarSimulacao = async () => {
    setSimulando(true);
    setErro(null);
    try {
      await api.simularLeitura(tipoSimulado, nomeSimulado);
      onSimulado();
      setModalSimular(false);
    } catch (e) {
      console.error("Erro ao simular:", e);
      setErro("Não foi possível simular a leitura. Verifique o servidor.");
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
          <div className={BOTAO_CHIP}>
            <span className={`w-2 h-2 rounded-full ${online ? "bg-emerald-500 animate-pulse" : "bg-rose-500"}`} />
            <span>{online ? "Servidor Ativo" : "Desconectado"}</span>
          </div>

          <div className={BOTAO_CHIP}>
            <IconCpu size={14} className="text-neutral-500" />
            <span>{status?.modelo_carregado ? `LBPH: ${status.total_identidades} pessoas` : "Modelo não treinado"}</span>
          </div>

          <Link
            href="/documentacao"
            className={`${BOTAO_CHIP} hover:bg-neutral-200 dark:hover:bg-neutral-700 transition-colors`}
            title="Features, regras de negócio e requisitos do sistema"
          >
            <IconBook size={14} className="text-neutral-500" />
            <span>Documentação</span>
          </Link>

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

      {modalSimular && (
        <Modal
          titulo="Simular Leitura da Portaria"
          descricao="Dispare um evento em tempo real para demonstrar o comportamento do sistema sem precisar do ESP32-CAM."
          onFechar={() => setModalSimular(false)}
          rodape={
            <div className="flex justify-end gap-2">
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
          }
        >
          <div>
            <span className="block text-xs font-medium text-neutral-700 dark:text-neutral-300 mb-1">Tipo de Resultado</span>
            <div className="grid grid-cols-3 gap-1.5">
              {OPCOES_SIMULACAO.map(({ tipo, rotulo, nomePadrao, Icone, classeAtiva }) => (
                <button
                  key={tipo}
                  type="button"
                  aria-pressed={tipoSimulado === tipo}
                  onClick={() => {
                    setTipoSimulado(tipo);
                    setNomeSimulado(nomePadrao);
                  }}
                  className={`py-1.5 text-xs font-medium rounded-md border flex items-center justify-center gap-1 ${
                    tipoSimulado === tipo
                      ? classeAtiva
                      : "border-neutral-200 dark:border-neutral-700 text-neutral-600 dark:text-neutral-400"
                  }`}
                >
                  <Icone size={12} /> {rotulo}
                </button>
              ))}
            </div>
          </div>

          {tipoSimulado !== "negado" && (
            <div>
              <label htmlFor="nome-simulado" className="block text-xs font-medium text-neutral-700 dark:text-neutral-300 mb-1">
                Nome da Pessoa
              </label>
              <input
                id="nome-simulado"
                type="text"
                maxLength={100}
                value={nomeSimulado}
                onChange={(e) => setNomeSimulado(e.target.value)}
                className="w-full text-xs px-2.5 py-1.5 rounded-md border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-800 text-neutral-900 dark:text-neutral-100 outline-none focus:ring-1 focus:ring-neutral-400"
              />
            </div>
          )}

          {erro && (
            <p role="alert" className="text-xs text-rose-600 dark:text-rose-400">
              {erro}
            </p>
          )}
        </Modal>
      )}
    </>
  );
}
