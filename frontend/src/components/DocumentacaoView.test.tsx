import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { diffLinhas, type VersaoDoc } from "@/lib/documentacao";
import { DocumentacaoView } from "./DocumentacaoView";

function versao(numero: number, nome: string, linhas: string[], anterior?: string[]): VersaoDoc {
  const diff = anterior ? diffLinhas(anterior, linhas) : linhas.map((texto) => ({ tipo: "igual" as const, texto }));
  return {
    numero,
    nome,
    linhas,
    diff,
    inicial: !anterior,
    adicoes: diff.filter((d) => d.tipo === "add").length,
    remocoes: diff.filter((d) => d.tipo === "rem").length,
  };
}

const V1 = ["# Doc", "## 1. Features", "- **F01** antiga", "- **F02** fica", "## 2. Regras", "- RN01 igual"];
const V2 = ["# Doc", "## 1. Features", "- **F02** fica", "- **F03** nova com `codigo`", "## 2. Regras", "- RN01 igual"];

// Mais nova primeiro, como a página entrega
const VERSOES = [versao(2, "V0002 05/11/2026", V2, V1), versao(1, "V0001 02/11/2026", V1)];

describe("DocumentacaoView", () => {
  it("abre na aba Main com a versão mais recente, sem destaques", () => {
    render(<DocumentacaoView versoes={VERSOES} />);

    expect(screen.getByRole("tab", { name: "Main", selected: true })).toBeInTheDocument();
    expect(screen.getByText("V0002 05/11/2026")).toBeInTheDocument();
    expect(screen.getByText("nova com", { exact: false })).toBeInTheDocument();
    expect(screen.queryByText("antiga", { exact: false })).not.toBeInTheDocument(); // linha removida não aparece
    expect(document.querySelector(".border-emerald-500")).toBeNull();
    expect(document.querySelector(".border-rose-500")).toBeNull();
  });

  it("renderiza título, negrito e código", () => {
    render(<DocumentacaoView versoes={VERSOES} />);
    expect(screen.getByRole("heading", { name: "Doc" })).toBeInTheDocument();
    expect(screen.getByText("F03").tagName).toBe("STRONG");
    expect(screen.getByText("codigo").tagName).toBe("CODE");
  });

  it("aba Log lista todas as versões, da mais nova para a mais antiga", async () => {
    const user = userEvent.setup();
    render(<DocumentacaoView versoes={VERSOES} />);

    await user.click(screen.getByRole("tab", { name: "Log" }));

    const nomes = screen.getAllByText(/^V000\d \d{2}\/\d{2}\/\d{4}$/).map((e) => e.textContent);
    expect(nomes).toEqual(["V0002 05/11/2026", "V0001 02/11/2026"]);
    expect(screen.getByText("atual")).toBeInTheDocument();
    expect(screen.getByText("versão inicial")).toBeInTheDocument();
  });

  it("adições aparecem em verde e remoções em vermelho, com contagem", async () => {
    const user = userEvent.setup();
    render(<DocumentacaoView versoes={VERSOES} />);
    await user.click(screen.getByRole("tab", { name: "Log" }));

    const atual = within(screen.getByText("V0002 05/11/2026").closest("details") as HTMLElement);
    const adicionada = atual.getByText("nova com", { exact: false }).closest(".border-emerald-500");
    const removida = atual.getByText("antiga", { exact: false }).closest(".border-rose-500");
    expect(adicionada).not.toBeNull();
    expect(removida).not.toBeNull();
    expect(removida).toHaveClass("line-through");
    expect(within(adicionada as HTMLElement).getByText("+")).toBeInTheDocument();
    expect(within(removida as HTMLElement).getByText("−")).toBeInTheDocument();
    expect(screen.getByText("+1")).toBeInTheDocument();
    expect(screen.getByText("−1")).toBeInTheDocument();
  });

  it("a versão inicial não tem destaques", async () => {
    const user = userEvent.setup();
    render(<DocumentacaoView versoes={[VERSOES[1]]} />);
    await user.click(screen.getByRole("tab", { name: "Log" }));
    expect(document.querySelector(".border-emerald-500, .border-rose-500")).toBeNull();
  });

  it("'Mostrar apenas alterações' esconde o que não mudou, mantendo o título da seção", async () => {
    const user = userEvent.setup();
    render(<DocumentacaoView versoes={VERSOES} />);
    await user.click(screen.getByRole("tab", { name: "Log" }));
    expect(screen.getAllByText("RN01 igual", { exact: false }).length).toBeGreaterThan(0);

    await user.click(screen.getByLabelText("Mostrar apenas alterações"));

    expect(screen.getByText("nova com", { exact: false })).toBeInTheDocument();
    expect(screen.getAllByText("1. Features").length).toBeGreaterThan(0); // contexto da alteração
    const detalhesAtual = screen.getByText("V0002 05/11/2026").closest("details") as HTMLElement;
    expect(within(detalhesAtual).queryByText("RN01 igual", { exact: false })).not.toBeInTheDocument();
    expect(within(detalhesAtual).queryByText("2. Regras")).not.toBeInTheDocument();
  });

  it("versão sem mudanças informa isso no modo só alterações", async () => {
    const igual = [versao(2, "V0002 05/11/2026", V1, V1), versao(1, "V0001 02/11/2026", V1)];
    const user = userEvent.setup();
    render(<DocumentacaoView versoes={igual} />);
    await user.click(screen.getByRole("tab", { name: "Log" }));
    await user.click(screen.getByLabelText("Mostrar apenas alterações"));
    expect(screen.getByText(/Nenhuma alteração em relação à versão anterior/)).toBeInTheDocument();
  });

  it("sem versões mostra aviso", () => {
    render(<DocumentacaoView versoes={[]} />);
    expect(screen.getByText(/Nenhuma versão da documentação encontrada/)).toBeInTheDocument();
  });

  it("HTML no texto da documentação é exibido como texto", () => {
    const perigosa = versao(1, "V0001 02/11/2026", ["# <script>alert(1)</script>", "- <img src=x onerror=alert(2)>"]);
    const { container } = render(<DocumentacaoView versoes={[perigosa]} />);
    expect(container.querySelector("script")).toBeNull();
    expect(container.querySelector("img")).toBeNull();
    expect(screen.getByText("<script>alert(1)</script>")).toBeInTheDocument();
  });
});
