import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api, type StatusSistema } from "@/services/api";
import { Header } from "./Header";

vi.mock("@/services/api", async (importOriginal) => {
  const real = await importOriginal<typeof import("@/services/api")>();
  return { ...real, api: { simularLeitura: vi.fn() } };
});

const onSimulado = vi.fn();
const status = { modelo_carregado: true, total_identidades: 3 } as StatusSistema;

beforeEach(() => {
  onSimulado.mockReset();
  vi.mocked(api.simularLeitura).mockReset().mockResolvedValue({ sucesso: true });
  vi.spyOn(console, "error").mockImplementation(() => {});
});

describe("Header", () => {
  it("mostra estado do servidor e do modelo", () => {
    const { rerender } = render(<Header status={status} online onSimulado={onSimulado} />);
    expect(screen.getByText("Servidor Ativo")).toBeInTheDocument();
    expect(screen.getByText("LBPH: 3 pessoas")).toBeInTheDocument();

    rerender(<Header status={null} online={false} onSimulado={onSimulado} />);
    expect(screen.getByText("Desconectado")).toBeInTheDocument();
    expect(screen.getByText("Modelo não treinado")).toBeInTheDocument();
  });

  it("tem link para a documentação", () => {
    render(<Header status={status} online onSimulado={onSimulado} />);
    expect(screen.getByRole("link", { name: /Documentação/ })).toHaveAttribute("href", "/documentacao");
  });

  it("dispara a simulação padrão (autorizado)", async () => {
    const user = userEvent.setup();
    render(<Header status={status} online onSimulado={onSimulado} />);

    await user.click(screen.getByRole("button", { name: /Simular Leitura/ }));
    await user.click(screen.getByRole("button", { name: "Disparar Leitura" }));

    expect(api.simularLeitura).toHaveBeenCalledWith("autorizado", "Marina Costa");
    await waitFor(() => expect(onSimulado).toHaveBeenCalled());
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("trocar o tipo ajusta o nome padrão e o desconhecido não pede nome", async () => {
    const user = userEvent.setup();
    render(<Header status={status} online onSimulado={onSimulado} />);
    await user.click(screen.getByRole("button", { name: /Simular Leitura/ }));

    await user.click(screen.getByRole("button", { name: /Revogado/ }));
    expect(screen.getByLabelText("Nome da Pessoa")).toHaveValue("Sérgio Baptista");

    await user.click(screen.getByRole("button", { name: /Desconhecido/ }));
    expect(screen.queryByLabelText("Nome da Pessoa")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Disparar Leitura" }));
    expect(api.simularLeitura).toHaveBeenCalledWith("negado", "Desconhecido");
  });

  it("erro do servidor mantém o modal aberto com aviso", async () => {
    vi.mocked(api.simularLeitura).mockRejectedValue(new Error("x"));
    const user = userEvent.setup();
    render(<Header status={status} online onSimulado={onSimulado} />);
    await user.click(screen.getByRole("button", { name: /Simular Leitura/ }));
    await user.click(screen.getByRole("button", { name: "Disparar Leitura" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/Não foi possível simular/);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(onSimulado).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Disparar Leitura" })).toBeEnabled();
  });
});
