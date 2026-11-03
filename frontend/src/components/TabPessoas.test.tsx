import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "@/services/api";
import { criarCaptura, criarUsuario } from "@/test/fabricas";
import { TabPessoas } from "./TabPessoas";

vi.mock("@/services/api", async (importOriginal) => {
  const real = await importOriginal<typeof import("@/services/api")>();
  return {
    ...real,
    api: { updateUsuarioStatus: vi.fn(), vincularCaptura: vi.fn(), treinarModelo: vi.fn() },
  };
});

const onRefresh = vi.fn();

beforeEach(() => {
  onRefresh.mockReset();
  vi.mocked(api.updateUsuarioStatus).mockReset().mockResolvedValue({ sucesso: true });
  vi.mocked(api.vincularCaptura).mockReset().mockResolvedValue({ sucesso: true, mensagem: "Vinculada!" });
  vi.mocked(api.treinarModelo).mockReset().mockResolvedValue({ sucesso: true, mensagem: "Treino iniciado" });
  vi.spyOn(console, "error").mockImplementation(() => {});
});

const renderizar = (usuarios = [criarUsuario()], capturas = [criarCaptura()]) =>
  render(<TabPessoas usuarios={usuarios} capturas={capturas} onRefresh={onRefresh} />);

describe("TabPessoas", () => {
  it("lista pessoas, status e quantidade de fotos", () => {
    renderizar([criarUsuario({ total_fotos: 12 }), criarUsuario({ id: 1, nome: "Bia", status: "revogado" })]);
    expect(screen.getByText("Pessoas cadastradas (2)")).toBeInTheDocument();
    expect(screen.getByText("(12 fotos)")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ativo" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Revogado" })).toBeInTheDocument();
  });

  it("mostra mensagens de lista vazia", () => {
    renderizar([], []);
    expect(screen.getByText(/Nenhuma pessoa cadastrada/)).toBeInTheDocument();
    expect(screen.getByText(/Nenhuma face desconhecida pendente/)).toBeInTheDocument();
  });

  it("alterna o status e atualiza a tela", async () => {
    const user = userEvent.setup();
    renderizar();

    await user.click(screen.getByRole("button", { name: "Ativo" }));

    expect(api.updateUsuarioStatus).toHaveBeenCalledWith(0, "revogado");
    await waitFor(() => expect(onRefresh).toHaveBeenCalled());
  });

  it("reativa uma pessoa revogada", async () => {
    const user = userEvent.setup();
    renderizar([criarUsuario({ status: "revogado" })]);
    await user.click(screen.getByRole("button", { name: "Revogado" }));
    expect(api.updateUsuarioStatus).toHaveBeenCalledWith(0, "ativo");
  });

  it("falha ao alterar status mostra aviso e não quebra a tela", async () => {
    vi.mocked(api.updateUsuarioStatus).mockRejectedValue(new Error("x"));
    const user = userEvent.setup();
    renderizar();

    await user.click(screen.getByRole("button", { name: "Ativo" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/alterar o status/);
    expect(onRefresh).not.toHaveBeenCalled();
    expect(screen.getByText("Pessoas cadastradas (1)")).toBeInTheDocument();
  });

  it("vincular: botão fica desabilitado sem nome e envia o nome sem espaços", async () => {
    const user = userEvent.setup();
    renderizar();

    await user.click(screen.getByRole("button", { name: "Vincular" }));
    const salvar = screen.getByRole("button", { name: "Salvar & Retreinar" });
    expect(salvar).toBeDisabled();

    await user.type(screen.getByLabelText("Nome da Pessoa"), "   ");
    expect(salvar).toBeDisabled();

    await user.type(screen.getByLabelText("Nome da Pessoa"), " Maria José ");
    expect(salvar).toBeEnabled();
    await user.click(salvar);

    expect(api.vincularCaptura).toHaveBeenCalledWith(7, "Maria José");
    expect(await screen.findByText("Vinculada!")).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(onRefresh).toHaveBeenCalled();
  });

  it("vincular: escolher pessoa existente preenche o nome", async () => {
    const user = userEvent.setup();
    renderizar([criarUsuario({ nome: "Bia Lima" })]);
    await user.click(screen.getByRole("button", { name: "Vincular" }));
    await user.click(screen.getByRole("button", { name: "Bia Lima" }));
    expect(screen.getByLabelText("Nome da Pessoa")).toHaveValue("Bia Lima");
  });

  it("vincular: erro mantém o modal aberto e avisa", async () => {
    vi.mocked(api.vincularCaptura).mockRejectedValue(new Error("x"));
    const user = userEvent.setup();
    renderizar();
    await user.click(screen.getByRole("button", { name: "Vincular" }));
    await user.type(screen.getByLabelText("Nome da Pessoa"), "Ana");
    await user.click(screen.getByRole("button", { name: "Salvar & Retreinar" }));

    expect(await screen.findByText(/Não foi possível vincular/)).toBeInTheDocument();
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("Esc e Cancelar fecham o modal", async () => {
    const user = userEvent.setup();
    renderizar();
    await user.click(screen.getByRole("button", { name: "Vincular" }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Vincular" }));
    await user.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("treinar: desabilita o botão e mostra o aviso do servidor", async () => {
    const user = userEvent.setup();
    renderizar();

    await user.click(screen.getByRole("button", { name: /Treinar Modelo/ }));

    expect(api.treinarModelo).toHaveBeenCalledTimes(1);
    expect(await screen.findByText("Treino iniciado")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Treinando/ })).toBeDisabled();
  });

  it("treinar: falha reabilita o botão e avisa", async () => {
    vi.mocked(api.treinarModelo).mockRejectedValue(new Error("x"));
    const user = userEvent.setup();
    renderizar();
    await user.click(screen.getByRole("button", { name: /Treinar Modelo/ }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/iniciar o treinamento/);
    expect(screen.getByRole("button", { name: /Treinar Modelo/ })).toBeEnabled();
  });

  it("nomes com HTML são exibidos como texto", () => {
    const { container } = renderizar([criarUsuario({ nome: '<img src=x onerror="alert(1)">' })]);
    expect(container.querySelector("img")).toBeNull();
    expect(screen.getByText('<img src=x onerror="alert(1)">')).toBeInTheDocument();
  });

  it("não deixa temporizadores pendentes ao desmontar", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      const { unmount } = renderizar();
      await user.click(screen.getByRole("button", { name: /Treinar Modelo/ }));
      await screen.findByText("Treino iniciado");
      unmount();
      act(() => vi.runAllTimers());
      expect(onRefresh).not.toHaveBeenCalled();
    } finally {
      vi.useRealTimers();
    }
  });
});
