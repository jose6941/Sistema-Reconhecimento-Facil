import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { criarLog } from "@/test/fabricas";
import { api } from "@/services/api";
import { TabHistorico, TAMANHO_PAGINA } from "./TabHistorico";

vi.mock("@/services/api", async (importOriginal) => {
  const real = await importOriginal<typeof import("@/services/api")>();
  return { ...real, api: { getLogs: vi.fn() } };
});

const getLogs = vi.mocked(api.getLogs);

function renderizar(props: Partial<React.ComponentProps<typeof TabHistorico>> = {}) {
  return render(<TabHistorico estatisticas={null} excecoes={[]} {...props} />);
}

const ultimaChamada = () => getLogs.mock.calls.at(-1)![0]!;

beforeEach(() => {
  getLogs.mockReset();
  getLogs.mockResolvedValue([]);
});

describe("TabHistorico (filtros no servidor)", () => {
  it("carrega a primeira página ao abrir, sem filtros", async () => {
    getLogs.mockResolvedValue([criarLog({ id: 1, usuario_nome: "Ana" }), criarLog({ id: 2, usuario_nome: "Bia" })]);
    renderizar();

    expect(await screen.findByText("Ana")).toBeInTheDocument();
    expect(screen.getByText("Bia")).toBeInTheDocument();
    expect(getLogs).toHaveBeenCalledTimes(1);
    expect(ultimaChamada()).toMatchObject({ limite: TAMANHO_PAGINA, usuario: undefined, status: undefined, excecoes: undefined });
    expect(screen.getByText(/Registro Geral de Auditoria \(2\)/)).toBeInTheDocument();
  });

  it("busca por nome com debounce: uma única chamada para o texto completo", async () => {
    const user = userEvent.setup();
    renderizar();
    await waitFor(() => expect(getLogs).toHaveBeenCalledTimes(1));

    await user.type(screen.getByLabelText("Filtrar por nome"), "ana");

    await waitFor(() => expect(ultimaChamada().usuario).toBe("ana"), { timeout: 2000 });
    const filtros = getLogs.mock.calls.map(([f]) => f?.usuario);
    expect(filtros).toEqual([undefined, "ana"]); // nenhuma chamada para "a" ou "an"
  });

  it("espaços em volta do nome são ignorados", async () => {
    const user = userEvent.setup();
    renderizar();
    await user.type(screen.getByLabelText("Filtrar por nome"), "  ana  ");
    await waitFor(() => expect(ultimaChamada().usuario).toBe("ana"), { timeout: 2000 });
  });

  it("filtro 'Apenas Exceções' envia excecoes=true e não envia status", async () => {
    const user = userEvent.setup();
    renderizar();
    await waitFor(() => expect(getLogs).toHaveBeenCalledTimes(1));

    await user.selectOptions(screen.getByLabelText("Filtrar por status"), "excecoes");

    await waitFor(() => expect(getLogs).toHaveBeenCalledTimes(2));
    expect(ultimaChamada()).toMatchObject({ excecoes: true, status: undefined });
  });

  it("filtro por status específico envia status", async () => {
    const user = userEvent.setup();
    renderizar();
    await user.selectOptions(screen.getByLabelText("Filtrar por status"), "revoked");
    await waitFor(() => expect(ultimaChamada()).toMatchObject({ status: "revoked", excecoes: undefined }));
  });

  it("filtros de período enviam as datas", async () => {
    renderizar();
    await waitFor(() => expect(getLogs).toHaveBeenCalledTimes(1));
    const user = userEvent.setup();

    await user.type(screen.getByLabelText("Data inicial"), "2026-03-01");
    await user.type(screen.getByLabelText("Data final"), "2026-03-31");

    await waitFor(() => expect(ultimaChamada()).toMatchObject({ data_inicio: "2026-03-01", data_fim: "2026-03-31" }));
  });

  it("'Carregar mais' usa offset e acumula os resultados", async () => {
    const primeira = Array.from({ length: TAMANHO_PAGINA }, (_, i) => criarLog({ id: i + 1, usuario_nome: `Pessoa ${i + 1}` }));
    getLogs.mockResolvedValueOnce(primeira).mockResolvedValueOnce([criarLog({ id: 999, usuario_nome: "Última Pessoa" })]);
    const user = userEvent.setup();
    renderizar();

    await user.click(await screen.findByRole("button", { name: "Carregar mais" }));

    expect(await screen.findByText("Última Pessoa")).toBeInTheDocument();
    expect(screen.getByText("Pessoa 1")).toBeInTheDocument(); // as anteriores continuam
    expect(ultimaChamada()).toMatchObject({ offset: TAMANHO_PAGINA, limite: TAMANHO_PAGINA });
    expect(screen.queryByRole("button", { name: "Carregar mais" })).not.toBeInTheDocument(); // página incompleta = fim
  });

  it("não mostra 'Carregar mais' quando a página não está cheia", async () => {
    getLogs.mockResolvedValue([criarLog()]);
    renderizar();
    await screen.findByText("Ana Souza");
    expect(screen.queryByRole("button", { name: "Carregar mais" })).not.toBeInTheDocument();
  });

  it("mostra erro e permite tentar de novo", async () => {
    getLogs.mockRejectedValueOnce(new Error("falhou")).mockResolvedValueOnce([criarLog({ usuario_nome: "Recuperada" })]);
    const user = userEvent.setup();
    renderizar();

    expect(await screen.findByRole("alert")).toHaveTextContent("Não foi possível carregar o histórico");
    await user.click(screen.getByRole("button", { name: "Tentar novamente" }));

    expect(await screen.findByText("Recuperada")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("recarrega quando chega um novo acesso (versaoDados muda)", async () => {
    const { rerender } = renderizar({ versaoDados: 0 });
    await waitFor(() => expect(getLogs).toHaveBeenCalledTimes(1));

    rerender(<TabHistorico estatisticas={null} excecoes={[]} versaoDados={1} />);

    await waitFor(() => expect(getLogs).toHaveBeenCalledTimes(2));
  });

  it("resposta antiga não sobrescreve a mais nova", async () => {
    let liberarAntiga!: (v: ReturnType<typeof criarLog>[]) => void;
    getLogs.mockImplementationOnce(() => new Promise((resolve) => (liberarAntiga = resolve)));
    getLogs.mockResolvedValueOnce([criarLog({ id: 2, usuario_nome: "Resultado Novo" })]);
    const user = userEvent.setup();
    renderizar();

    await user.selectOptions(screen.getByLabelText("Filtrar por status"), "denied");
    expect(await screen.findByText("Resultado Novo")).toBeInTheDocument();

    liberarAntiga([criarLog({ id: 1, usuario_nome: "Resultado Antigo" })]);
    await new Promise((r) => setTimeout(r, 20));

    expect(screen.queryByText("Resultado Antigo")).not.toBeInTheDocument();
    expect(screen.getByText("Resultado Novo")).toBeInTheDocument();
  });

  it("mostra estatísticas e exceções recentes", async () => {
    renderizar({
      estatisticas: {
        entradas_hoje: 12,
        falsos_aceitos_pct: 2.5,
        falsos_rejeitados_pct: 3.5,
      } as never,
      excecoes: [criarLog({ id: 5, usuario_nome: "Intruso", status: "denied" })],
    });
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByText("2.5%")).toBeInTheDocument();
    expect(screen.getByText("Intruso")).toBeInTheDocument();
    await waitFor(() => expect(getLogs).toHaveBeenCalled());
  });

  it("nomes com HTML são exibidos como texto (sem criar elementos)", async () => {
    getLogs.mockResolvedValue([criarLog({ usuario_nome: '<img src=x onerror="alert(1)"><script>alert(2)</script>' })]);
    const { container } = renderizar();

    expect(await screen.findByText(/<script>alert\(2\)<\/script>/)).toBeInTheDocument();
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("script")).toBeNull();
  });

  it("não inventa confiança para registros sem valor", async () => {
    getLogs.mockResolvedValue([criarLog({ status: "authorized", confianca: 0, distancia_lbph: null })]);
    renderizar();
    await screen.findByText("Ana Souza");
    expect(screen.queryByText("96%")).not.toBeInTheDocument();
  });
});
