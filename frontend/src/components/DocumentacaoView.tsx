"use client";

import { Fragment, type ReactNode, useState } from "react";
import { TabButton } from "@/components/TabButton";
import type { LinhaDiff, TipoLinha, VersaoDoc } from "@/lib/documentacao";

interface DocumentacaoViewProps {
  /** Versões em ordem decrescente: a primeira é a mais recente. */
  versoes: VersaoDoc[];
}

/** Renderiza trechos em **negrito** e `código` dentro de uma linha. */
function Inline({ texto }: { texto: string }) {
  const partes = texto.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).filter(Boolean);
  return (
    <>
      {partes.map((p, i) => {
        if (p.startsWith("**") && p.endsWith("**")) {
          return (
            <strong key={i} className="font-semibold">
              {p.slice(2, -2)}
            </strong>
          );
        }
        if (p.startsWith("`") && p.endsWith("`")) {
          return (
            <code
              key={i}
              className="px-1 py-0.5 rounded bg-neutral-200/70 dark:bg-neutral-800 font-mono text-[11px]"
            >
              {p.slice(1, -1)}
            </code>
          );
        }
        return <Fragment key={i}>{p}</Fragment>;
      })}
    </>
  );
}

const ESTILO_DIFF: Record<TipoLinha, string> = {
  igual: "",
  add: "bg-emerald-50 dark:bg-emerald-950/40 border-l-2 border-emerald-500 text-emerald-900 dark:text-emerald-200",
  rem: "bg-rose-50 dark:bg-rose-950/40 border-l-2 border-rose-500 text-rose-900 dark:text-rose-200 line-through decoration-rose-400/60",
};

const SINAL_DIFF: Record<TipoLinha, string> = { igual: "", add: "+", rem: "−" };

function Linha({ linha, comDiff }: { linha: LinhaDiff; comDiff: boolean }) {
  const { texto } = linha;
  const destaque = comDiff ? ESTILO_DIFF[linha.tipo] : "";
  const sinal = comDiff && linha.tipo !== "igual" ? SINAL_DIFF[linha.tipo] : null;

  let conteudo: ReactNode;
  let espacamento = "py-0.5";

  if (texto.startsWith("# ")) {
    conteudo = <h2 className="text-lg font-semibold tracking-tight">{texto.slice(2)}</h2>;
    espacamento = "py-1";
  } else if (texto.startsWith("## ")) {
    conteudo = <h3 className="text-[15px] font-semibold">{texto.slice(3)}</h3>;
    espacamento = "pt-4 pb-1";
  } else if (texto.startsWith("### ")) {
    conteudo = <h4 className="text-[13px] font-semibold text-neutral-600 dark:text-neutral-300">{texto.slice(4)}</h4>;
    espacamento = "pt-2 pb-0.5";
  } else if (texto.startsWith("- ")) {
    conteudo = (
      <div className="flex gap-2 text-[13px] leading-relaxed pl-2">
        <span aria-hidden className="text-neutral-400">•</span>
        <span>
          <Inline texto={texto.slice(2)} />
        </span>
      </div>
    );
  } else {
    conteudo = (
      <p className="text-[13px] leading-relaxed">
        <Inline texto={texto} />
      </p>
    );
  }

  return (
    <div className={`flex items-start gap-2 px-2 rounded-sm ${espacamento} ${destaque}`}>
      {comDiff && (
        <span aria-hidden className="w-3 shrink-0 font-mono text-[12px] select-none pt-0.5">
          {sinal}
        </span>
      )}
      <div className="min-w-0 flex-1">{conteudo}</div>
    </div>
  );
}

/** Mantém só as linhas alteradas, acrescidas dos títulos que as contextualizam. */
function somenteAlteracoes(diff: LinhaDiff[]): LinhaDiff[] {
  const saida: LinhaDiff[] = [];
  let pendentes: LinhaDiff[] = [];

  for (const l of diff) {
    const ehTitulo = l.texto.startsWith("#");
    if (l.tipo === "igual") {
      if (ehTitulo) {
        pendentes = l.texto.startsWith("### ")
          ? [...pendentes.filter((p) => !p.texto.startsWith("### ")), l]
          : [l];
      }
      continue;
    }
    saida.push(...pendentes);
    pendentes = [];
    saida.push(l);
  }
  return saida;
}

export function DocumentacaoView({ versoes }: DocumentacaoViewProps) {
  const [aba, setAba] = useState<"main" | "log">("main");
  const [apenasAlteracoes, setApenasAlteracoes] = useState(false);

  const atual = versoes[0];

  if (!atual) {
    return (
      <p className="text-xs text-neutral-400 py-8 text-center">
        Nenhuma versão da documentação encontrada em <code>src/content/documentacao/</code>.
      </p>
    );
  }

  return (
    <div>
      <div className="flex gap-2 mb-4" role="tablist">
        <TabButton ativa={aba === "main"} onClick={() => setAba("main")}>
          Main
        </TabButton>
        <TabButton ativa={aba === "log"} onClick={() => setAba("log")}>
          Log
        </TabButton>
      </div>

      {aba === "main" && (
        <section className="bg-neutral-100/70 dark:bg-neutral-900/60 border border-neutral-200/80 dark:border-neutral-800 rounded-xl p-4">
          <p className="text-[12px] text-neutral-500 dark:text-neutral-400 mb-3">
            Versão mais recente: <span className="font-mono font-medium">{atual.nome}</span>
          </p>
          {atual.linhas.map((texto, i) => (
            <Linha key={i} linha={{ tipo: "igual", texto }} comDiff={false} />
          ))}
        </section>
      )}

      {aba === "log" && (
        <section className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-3 text-[12px] text-neutral-500 dark:text-neutral-400">
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-sm bg-emerald-500" /> Adicionado
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-sm bg-rose-500" /> Removido
              </span>
            </div>
            <label className="flex items-center gap-1.5 text-[12px] text-neutral-600 dark:text-neutral-300 cursor-pointer">
              <input
                type="checkbox"
                checked={apenasAlteracoes}
                onChange={(e) => setApenasAlteracoes(e.target.checked)}
              />
              Mostrar apenas alterações
            </label>
          </div>

          {versoes.map((v, idx) => {
            const linhas = apenasAlteracoes && !v.inicial ? somenteAlteracoes(v.diff) : v.diff;
            return (
              <details
                key={v.numero}
                open={idx === 0}
                className="bg-neutral-100/70 dark:bg-neutral-900/60 border border-neutral-200/80 dark:border-neutral-800 rounded-xl p-3"
              >
                <summary className="cursor-pointer flex flex-wrap items-center gap-2 text-[13px] font-medium text-neutral-800 dark:text-neutral-200">
                  <span className="font-mono">{v.nome}</span>
                  {idx === 0 && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded border border-neutral-300 dark:border-neutral-700 text-neutral-500">
                      atual
                    </span>
                  )}
                  {v.inicial ? (
                    <span className="text-[11px] font-normal text-neutral-500">versão inicial</span>
                  ) : (
                    <>
                      <span className="text-[11px] font-mono text-emerald-600 dark:text-emerald-400">+{v.adicoes}</span>
                      <span className="text-[11px] font-mono text-rose-600 dark:text-rose-400">−{v.remocoes}</span>
                    </>
                  )}
                </summary>

                <div className="mt-3">
                  {linhas.length === 0 ? (
                    <p className="text-xs text-neutral-400 py-2">Nenhuma alteração em relação à versão anterior.</p>
                  ) : (
                    linhas.map((l, i) => <Linha key={i} linha={l} comDiff={!v.inicial} />)
                  )}
                </div>
              </details>
            );
          })}
        </section>
      )}
    </div>
  );
}
