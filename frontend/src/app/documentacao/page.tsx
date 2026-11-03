import type { Metadata } from "next";
import Link from "next/link";
import { carregarVersoes } from "@/lib/documentacao";
import { DocumentacaoView } from "@/components/DocumentacaoView";

export const metadata: Metadata = {
  title: "Documentação | Sistema de Reconhecimento Facial (TCC IFSP)",
  description: "Features, regras de negócio e requisitos do sistema, com o histórico de versões.",
};

export default async function PaginaDocumentacao() {
  // Do mais recente para o mais antigo
  const versoes = (await carregarVersoes()).reverse();

  return (
    <main className="min-h-screen bg-neutral-50 dark:bg-neutral-950 text-neutral-900 dark:text-neutral-100 p-4 md:p-6 transition-colors">
      <div className="max-w-4xl mx-auto">
        <header className="flex items-center justify-between gap-3 pb-4 mb-4 border-b border-neutral-200 dark:border-neutral-800">
          <div>
            <h1 className="text-base md:text-lg font-semibold tracking-tight">Documentação</h1>
            <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-0.5">
              Features, regras de negócio e requisitos do sistema
            </p>
          </div>
          <Link
            href="/"
            className="text-xs px-2.5 py-1 rounded-md bg-neutral-100 dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700 text-neutral-700 dark:text-neutral-300 hover:bg-neutral-200 dark:hover:bg-neutral-700 transition-colors"
          >
            ← Voltar ao painel
          </Link>
        </header>

        <DocumentacaoView versoes={versoes} />

        <footer className="mt-8 pt-4 border-t border-neutral-200 dark:border-neutral-800 text-center text-xs text-neutral-400 dark:text-neutral-500">
          Trabalho de Conclusão de Curso · Sistema de Reconhecimento Facial de Baixo Custo com ESP32-CAM · IFSP Câmpus Birigui
        </footer>
      </div>
    </main>
  );
}
