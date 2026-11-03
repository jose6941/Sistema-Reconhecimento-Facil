"use client";

import { useEffect, useId, type ReactNode } from "react";

interface ModalProps {
  titulo: string;
  descricao?: string;
  children: ReactNode;
  /** Botões do rodapé. */
  rodape: ReactNode;
  /** Chamado ao pressionar Esc. */
  onFechar?: () => void;
}

/** Caixa de diálogo padrão do painel (substitui três modais com o mesmo markup). */
export function Modal({ titulo, descricao, children, rodape, onFechar }: ModalProps) {
  const idTitulo = useId();

  useEffect(() => {
    if (!onFechar) return;
    const aoPressionar = (e: KeyboardEvent) => {
      if (e.key === "Escape") onFechar();
    };
    document.addEventListener("keydown", aoPressionar);
    return () => document.removeEventListener("keydown", aoPressionar);
  }, [onFechar]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-xs p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={idTitulo}
        className="bg-white dark:bg-neutral-900 rounded-xl border border-neutral-200 dark:border-neutral-800 max-w-sm w-full p-5 shadow-xl"
      >
        <h3 id={idTitulo} className="text-sm font-semibold text-neutral-900 dark:text-neutral-100 mb-1">
          {titulo}
        </h3>
        {descricao && <p className="text-xs text-neutral-500 dark:text-neutral-400 mb-4">{descricao}</p>}
        <div className="space-y-3">{children}</div>
        <div className="mt-5">{rodape}</div>
      </div>
    </div>
  );
}
