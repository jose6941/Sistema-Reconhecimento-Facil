import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "@/services/api";
import { criarLog, criarUsuario } from "@/test/fabricas";
import Home from "./page";

vi.mock("@/services/api", async (importOriginal) => {
  const real = await importOriginal<typeof import("@/services/api")>();
  return {
    ...real,
    api: {
      getStatus: vi.fn(),
      getLogsRecentes: vi.fn(),
      getExcecoes: vi.fn(),
      getUsuarios: vi.fn(),
      getCapturasDesconhecidas: vi.fn(),
      getEstatisticas: vi.fn(),
      getLogs: vi.fn(),
      getCameraInfo: vi.fn(),
      simularLeitura: vi.fn(),
    },
  };
});

class EventSourceFalso {
  static instancias: EventSourceFalso[] = [];
  onmessage: ((e: { data: string }) => void) | null = null;
  fechado = false;
  constructor(public url: string) {
    EventSourceFalso.instancias.push(this);
  }
  close() {
    this.fechado = true;
  }
  emitir(dados: unknown) {
    this.onmessage?.({ data: typeof dados === "string" ? dados : JSON.stringify(dados) });
  }
}

const STATUS = {
  status: "online",
  modelo_carregado: true,
  total_identidades: 2,
  limiar_lbph: 65,
  camera_id: "CAM-01 · Portaria",
  ultimo_reconhecimento: { status: "idle", user: null, user_id: null, confidence: 0, data_hora: null, foto_url: null, camera_id: "x" },
};

beforeEach(() => {
  EventSourceFalso.instancias = [];
  vi.stubGlobal("EventSource", EventSourceFalso);
  vi.mocked(api.getStatus).mockReset().mockResolvedValue(STATUS);
  vi.mocked(api.getLogsRecentes).mockReset().mockResolvedValue([criarLog({ usuario_nome: "Entrada Recente" })]);
  vi.mocked(api.getExcecoes).mockReset().mockResolvedValue([]);
  vi.mocked(api.getUsuarios).mockReset().mockResolvedValue([criarUsuario({ nome: "Pessoa Cadastrada" })]);
  vi.mocked(api.getCapturasDesconhecidas).mockReset().mockResolvedValue([]);
  vi.mocked(api.getEstatisticas).mockReset().mockResolvedValue(null as never);
  vi.mocked(api.getLogs).mockReset().mockResolvedValue([]);
  vi.mocked(api.getCameraInfo).mockReset().mockResolvedValue({ conectado: false, url: null, fps: 0, ultimo_frame_ts: null });
  vi.spyOn(console, "error").mockImplementation(() => {});
});

afterEach(() => vi.unstubAllGlobals());

describe("Home (painel)", () => {
  it("carrega os dados e mostra a aba Ao vivo", async () => {
    render(<Home />);
    expect(await screen.findByText("Entrada Recente")).toBeInTheDocument();
    expect(screen.getByText("Servidor Ativo")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Ao vivo", selected: true })).toBeInTheDocument();
    expect(EventSourceFalso.instancias).toHaveLength(1);
    expect(EventSourceFalso.instancias[0].url).toMatch(/\/api\/eventos$/);
  });

  it("não busca o histórico completo na carga inicial (só quando a aba abre)", async () => {
    const user = userEvent.setup();
    render(<Home />);
    await screen.findByText("Entrada Recente");
    expect(api.getLogs).not.toHaveBeenCalled();

    await user.click(screen.getByRole("tab", { name: "Histórico" }));

    await waitFor(() => expect(api.getLogs).toHaveBeenCalledTimes(1));
  });

  it("navega entre as abas", async () => {
    const user = userEvent.setup();
    render(<Home />);
    await user.click(screen.getByRole("tab", { name: "Pessoas" }));
    expect(await screen.findByText("Pessoa Cadastrada")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Pessoas", selected: true })).toBeInTheDocument();
  });

  it("servidor offline: mostra 'Desconectado' sem quebrar", async () => {
    vi.mocked(api.getStatus).mockRejectedValue(new Error("offline"));
    vi.mocked(api.getLogsRecentes).mockRejectedValue(new Error("offline"));
    render(<Home />);
    expect(await screen.findByText("Desconectado")).toBeInTheDocument();
    expect(screen.getByText("Nenhuma entrada registrada hoje.")).toBeInTheDocument();
  });

  it("novo acesso por SSE recarrega os dados e o histórico filtrado", async () => {
    const user = userEvent.setup();
    render(<Home />);
    await user.click(screen.getByRole("tab", { name: "Histórico" }));
    await waitFor(() => expect(api.getLogs).toHaveBeenCalledTimes(1));
    const consultasAntes = vi.mocked(api.getStatus).mock.calls.length;

    act(() => EventSourceFalso.instancias[0].emitir({ tipo: "novo_acesso", dados: {} }));

    await waitFor(() => expect(api.getLogs).toHaveBeenCalledTimes(2));
    expect(vi.mocked(api.getStatus).mock.calls.length).toBeGreaterThan(consultasAntes);
  });

  it("fim do treinamento por SSE também recarrega", async () => {
    render(<Home />);
    await screen.findByText("Entrada Recente");
    const antes = vi.mocked(api.getUsuarios).mock.calls.length;

    act(() => EventSourceFalso.instancias[0].emitir({ tipo: "treinamento_concluido", dados: {} }));

    await waitFor(() => expect(vi.mocked(api.getUsuarios).mock.calls.length).toBeGreaterThan(antes));
  });

  it("eventos desconhecidos ou malformados são ignorados", async () => {
    render(<Home />);
    await screen.findByText("Entrada Recente");
    const antes = vi.mocked(api.getStatus).mock.calls.length;

    act(() => {
      EventSourceFalso.instancias[0].emitir({ tipo: "init", dados: {} });
      EventSourceFalso.instancias[0].emitir("isto não é JSON {{{");
      EventSourceFalso.instancias[0].emitir(null);
    });

    expect(vi.mocked(api.getStatus).mock.calls.length).toBe(antes);
    expect(screen.getByText("Servidor Ativo")).toBeInTheDocument();
  });

  it("fecha a conexão SSE e para a consulta periódica ao desmontar", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      const { unmount } = render(<Home />);
      await act(async () => {
        await vi.advanceTimersByTimeAsync(10);
      });
      const fonte = EventSourceFalso.instancias[0];

      unmount();
      const chamadas = vi.mocked(api.getStatus).mock.calls.length;
      await vi.advanceTimersByTimeAsync(30_000);

      expect(fonte.fechado).toBe(true);
      expect(vi.mocked(api.getStatus).mock.calls.length).toBe(chamadas);
    } finally {
      vi.useRealTimers();
    }
  });
});
