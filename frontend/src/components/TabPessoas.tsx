"use client";

import React, { useState } from "react";
import { IconCpu, IconRefresh, IconUserCheck, IconUserX, IconLink } from "@tabler/icons-react";
import { Usuario, CapturaDesconhecida, api } from "@/services/api";

interface TabPessoasProps {
  usuarios: Usuario[];
  capturas: CapturaDesconhecida[];
  onRefresh: () => void;
}

export function TabPessoas({ usuarios, capturas, onRefresh }: TabPessoasProps) {
  const [modalVincular, setModalVincular] = useState<CapturaDesconhecida | null>(null);
  const [nomePessoa, setNomePessoa] = useState("");
  const [vinculando, setVinculando] = useState(false);
  const [treinando, setTreinando] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);

  // Formata data de cadastro ou última entrada
  const formatarData = (isoString?: string | null) => {
    if (!isoString) return "—";
    const data = new Date(isoString);
    const hoje = new Date();
    const ehHoje =
      data.getDate() === hoje.getDate() &&
      data.getMonth() === hoje.getMonth() &&
      data.getFullYear() === hoje.getFullYear();

    if (ehHoje) {
      return `Hoje ${data.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}`;
    }
    return data.toLocaleDateString("pt-BR", { day: "2-digit", month: "short" });
  };

  const handleToggleStatus = async (usuario: Usuario) => {
    const novoStatus = usuario.status === "ativo" ? "revogado" : "ativo";
    try {
      await api.updateUsuarioStatus(usuario.id, novoStatus);
      onRefresh();
    } catch (e) {
      console.error("Erro ao alterar status:", e);
    }
  };

  const handleVincular = async () => {
    if (!modalVincular || !nomePessoa.trim()) return;
    setVinculando(true);
    try {
      const res = await api.vincularCaptura(modalVincular.id, nomePessoa.trim());
      setFeedback(res.mensagem || "Face vinculada com sucesso!");
      setNomePessoa("");
      setModalVincular(null);
      onRefresh();
      setTimeout(() => setFeedback(null), 4000);
    } catch (e) {
      console.error("Erro ao vincular:", e);
    } finally {
      setVinculando(false);
    }
  };

  const handleTreinarModelo = async () => {
    setTreinando(true);
    try {
      const res = await api.treinarModelo();
      setFeedback(res.mensagem);
      setTimeout(() => {
        setFeedback(null);
        setTreinando(false);
        onRefresh();
      }, 3000);
    } catch (e) {
      console.error("Erro ao treinar:", e);
      setTreinando(false);
    }
  };

  return (
    <div className="space-y-3">
      {/* Feedback de Ação */}
      {feedback && (
        <div className="p-2.5 rounded-lg bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-emerald-800 dark:text-emerald-300 text-xs flex justify-between items-center">
          <span>{feedback}</span>
          <button onClick={() => setFeedback(null)} className="text-emerald-600 font-bold ml-2">
            ✕
          </button>
        </div>
      )}

      {/* Tabela de Usuários Cadastrados */}
      <div className="bg-neutral-100/70 dark:bg-neutral-900/60 border border-neutral-200/80 dark:border-neutral-800 rounded-xl p-3">
        <div className="flex justify-between items-center pb-2 mb-1">
          <p className="text-[13px] text-neutral-600 dark:text-neutral-400 font-medium">
            Pessoas cadastradas ({usuarios.length})
          </p>
          <button
            onClick={handleTreinarModelo}
            disabled={treinando}
            className="flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-md bg-neutral-200 hover:bg-neutral-300 dark:bg-neutral-800 dark:hover:bg-neutral-700 text-neutral-800 dark:text-neutral-200 transition-colors disabled:opacity-50"
            title="Treinar classificador LBPH com as fotos do dataset"
          >
            <IconCpu size={13} className={treinando ? "animate-spin" : ""} />
            <span>{treinando ? "Treinando..." : "Treinar Modelo"}</span>
          </button>
        </div>

        {/* Cabeçalho da Tabela */}
        <div className="flex text-[12px] text-neutral-400 dark:text-neutral-500 px-1 py-1.5 font-medium border-b border-neutral-200 dark:border-neutral-800">
          <span className="flex-2">Nome</span>
          <span className="flex-1">Cadastro</span>
          <span className="flex-1">Última entrada</span>
          <span className="flex-1 text-right">Status</span>
        </div>

        {/* Linhas de Usuários */}
        <div className="flex flex-col">
          {usuarios.length === 0 ? (
            <div className="py-8 text-center text-xs text-neutral-400">
              Nenhuma pessoa cadastrada no modelo ainda.
            </div>
          ) : (
            usuarios.map((u) => {
              const isAtivo = u.status === "ativo";
              return (
                <div
                  key={u.id}
                  className="flex items-center px-1 py-2 border-b border-neutral-200/50 dark:border-neutral-800/50 last:border-0 text-[13px]"
                >
                  <div className="flex-2 flex items-center gap-2">
                    <div className="w-6 h-6 rounded-full bg-neutral-200 dark:bg-neutral-700 flex items-center justify-center text-[11px] font-semibold text-neutral-700 dark:text-neutral-300 shrink-0">
                      {u.nome.charAt(0).toUpperCase()}
                    </div>
                    <div>
                      <span className="text-neutral-800 dark:text-neutral-200 font-medium">
                        {u.nome}
                      </span>
                      {u.total_fotos !== undefined && u.total_fotos > 0 && (
                        <span className="text-[11px] text-neutral-400 ml-1.5">
                          ({u.total_fotos} fotos)
                        </span>
                      )}
                    </div>
                  </div>

                  <span className="flex-1 text-neutral-500 dark:text-neutral-400 text-xs">
                    {formatarData(u.data_cadastro)}
                  </span>

                  <span className="flex-1 text-neutral-500 dark:text-neutral-400 text-xs">
                    {formatarData(u.ultima_entrada)}
                  </span>

                  <span className="flex-1 text-right">
                    <button
                      onClick={() => handleToggleStatus(u)}
                      className={`text-[11px] px-2 py-0.5 rounded-md font-medium border transition-all cursor-pointer ${
                        isAtivo
                          ? "bg-emerald-50 dark:bg-emerald-950/50 text-emerald-700 dark:text-emerald-400 border-emerald-200 dark:border-emerald-800 hover:bg-emerald-100"
                          : "bg-rose-50 dark:bg-rose-950/50 text-rose-700 dark:text-rose-400 border-rose-200 dark:border-rose-800 hover:bg-rose-100"
                      }`}
                      title="Clique para alternar entre Ativo e Revogado"
                    >
                      {isAtivo ? "Ativo" : "Revogado"}
                    </button>
                  </span>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Seção Capturas sem Cadastro */}
      <div className="bg-neutral-100/70 dark:bg-neutral-900/60 border border-neutral-200/80 dark:border-neutral-800 rounded-xl p-3">
        <div className="flex justify-between items-center mb-2.5">
          <p className="text-[13px] text-neutral-600 dark:text-neutral-400 font-medium">
            Capturas sem cadastro
          </p>
          <span className="text-[11px] text-neutral-400">
            {capturas.length} detectadas pela câmera
          </span>
        </div>

        {capturas.length === 0 ? (
          <p className="text-xs text-neutral-400 py-3">
            Nenhuma face desconhecida pendente no momento.
          </p>
        ) : (
          <div className="flex gap-2 flex-wrap">
            {capturas.map((cap) => {
              const hora = new Date(cap.data_hora).toLocaleTimeString("pt-BR", {
                hour: "2-digit",
                minute: "2-digit",
              });
              return (
                <div
                  key={cap.id}
                  className="flex items-center gap-2 border border-neutral-300 dark:border-neutral-700 bg-white/70 dark:bg-neutral-800/80 rounded-md px-2.5 py-1.5 shadow-2xs"
                >
                  <span className="text-[13px] text-neutral-800 dark:text-neutral-200 font-medium">
                    #{cap.id} · {hora}
                  </span>
                  <button
                    onClick={() => {
                      setModalVincular(cap);
                      setNomePessoa("");
                    }}
                    className="text-[12px] px-2 py-0.5 rounded border border-neutral-300 dark:border-neutral-600 hover:bg-neutral-100 dark:hover:bg-neutral-700 text-neutral-700 dark:text-neutral-200 transition-colors"
                  >
                    Vincular
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Modal para Vincular Captura */}
      {modalVincular && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-xs p-4">
          <div className="bg-white dark:bg-neutral-900 rounded-xl border border-neutral-200 dark:border-neutral-800 max-w-sm w-full p-5 shadow-xl">
            <h3 className="text-sm font-semibold text-neutral-900 dark:text-neutral-100 mb-1">
              Vincular Captura #{modalVincular.id}
            </h3>
            <p className="text-xs text-neutral-500 dark:text-neutral-400 mb-4">
              Informe o nome da pessoa correspondente a este rosto. A foto será adicionada ao dataset e o modelo LBPH será retreinado automaticamente.
            </p>

            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-neutral-700 dark:text-neutral-300 mb-1">
                  Nome da Pessoa
                </label>
                <input
                  type="text"
                  placeholder="Ex: Marina Costa"
                  value={nomePessoa}
                  onChange={(e) => setNomePessoa(e.target.value)}
                  className="w-full text-xs px-2.5 py-2 rounded-md border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-800 text-neutral-900 dark:text-neutral-100 outline-none focus:ring-1 focus:ring-neutral-400"
                  autoFocus
                />
              </div>

              {usuarios.length > 0 && (
                <div>
                  <label className="block text-[11px] text-neutral-400 mb-1">
                    Ou selecione um usuário já existente:
                  </label>
                  <div className="flex flex-wrap gap-1 max-h-24 overflow-y-auto">
                    {usuarios.map((u) => (
                      <button
                        key={u.id}
                        type="button"
                        onClick={() => setNomePessoa(u.nome)}
                        className="text-[11px] px-2 py-0.5 rounded bg-neutral-100 dark:bg-neutral-800 hover:bg-neutral-200 dark:hover:bg-neutral-700 text-neutral-700 dark:text-neutral-300"
                      >
                        {u.nome}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className="flex justify-end gap-2 mt-5">
              <button
                type="button"
                onClick={() => setModalVincular(null)}
                className="px-3 py-1.5 text-xs rounded-md text-neutral-600 dark:text-neutral-400 hover:bg-neutral-100 dark:hover:bg-neutral-800"
              >
                Cancelar
              </button>
              <button
                type="button"
                disabled={vinculando || !nomePessoa.trim()}
                onClick={handleVincular}
                className="px-3 py-1.5 text-xs font-medium rounded-md bg-neutral-900 text-white dark:bg-neutral-100 dark:text-neutral-900 hover:opacity-90 disabled:opacity-50"
              >
                {vinculando ? "Vinculando..." : "Salvar & Retreinar"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
