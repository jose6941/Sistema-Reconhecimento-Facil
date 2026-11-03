import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, API_BASE_URL, montarQueryLogs } from "./api";

const fetchMock = vi.fn();

function responder(corpo: unknown, ok = true) {
  fetchMock.mockResolvedValueOnce({ ok, json: async () => corpo });
}

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => vi.unstubAllGlobals());

describe("montarQueryLogs", () => {
  it("omite filtros vazios", () => {
    expect(montarQueryLogs()).toBe("");
    expect(montarQueryLogs({ usuario: "", status: undefined, excecoes: false, offset: 0 })).toBe("");
  });

  it("inclui todos os filtros informados", () => {
    const query = new URLSearchParams(
      montarQueryLogs({
        usuario: "ana",
        status: "revoked",
        data_inicio: "2026-03-01",
        data_fim: "2026-03-31",
        excecoes: true,
        limite: 50,
        offset: 100,
      }),
    );
    expect(Object.fromEntries(query)).toEqual({
      usuario: "ana",
      status: "revoked",
      data_inicio: "2026-03-01",
      data_fim: "2026-03-31",
      excecoes: "true",
      limite: "50",
      offset: "100",
    });
  });

  it("codifica caracteres especiais (sem injeção de parâmetros)", () => {
    const query = montarQueryLogs({ usuario: "ana&status=denied#x=1 %" });
    expect(query).not.toContain("&status=denied");
    expect(new URLSearchParams(query).get("usuario")).toBe("ana&status=denied#x=1 %");
    expect([...new URLSearchParams(query).keys()]).toEqual(["usuario"]);
  });
});

describe("api", () => {
  it("getLogs chama a URL com os filtros", async () => {
    responder([]);
    await api.getLogs({ usuario: "ana", excecoes: true, limite: 50, offset: 50 });
    const url = new URL(fetchMock.mock.calls[0][0]);
    expect(`${url.origin}${url.pathname}`).toBe(`${API_BASE_URL}/api/logs`);
    expect(url.searchParams.get("excecoes")).toBe("true");
    expect(url.searchParams.get("offset")).toBe("50");
  });

  it("devolve o JSON da resposta", async () => {
    responder({ status: "online" });
    await expect(api.getStatus()).resolves.toEqual({ status: "online" });
  });

  it.each([
    ["getStatus", () => api.getStatus(), /status do sistema/],
    ["getLogs", () => api.getLogs(), /logs/],
    ["getUsuarios", () => api.getUsuarios(), /usuários/],
    ["treinarModelo", () => api.treinarModelo(), /treino/],
    ["conectarCamera", () => api.conectarCamera("http://x"), /conectar câmera/],
  ])("%s lança erro quando a API responde com falha", async (_nome, chamar, mensagem) => {
    responder({ erro: "x" }, false);
    await expect(chamar()).rejects.toThrow(mensagem);
  });

  it("propaga falha de rede", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("Failed to fetch"));
    await expect(api.getEstatisticas()).rejects.toThrow("Failed to fetch");
  });

  it("updateUsuarioStatus envia PATCH com JSON", async () => {
    responder({ sucesso: true });
    await api.updateUsuarioStatus(3, "revogado");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`${API_BASE_URL}/api/usuarios/3/status`);
    expect(init).toMatchObject({ method: "PATCH", headers: { "Content-Type": "application/json" } });
    expect(JSON.parse(init.body)).toEqual({ status: "revogado" });
  });

  it("vincularCaptura e simularLeitura enviam o corpo esperado", async () => {
    responder({ sucesso: true, mensagem: "ok" });
    await api.vincularCaptura(7, "Maria José");
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ captura_id: 7, nome_pessoa: "Maria José" });

    responder({ sucesso: true });
    await api.simularLeitura("negado", "X");
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({ tipo: "negado", nome: "X" });
  });

  it("treinarModelo e desconectarCamera usam POST sem corpo", async () => {
    responder({ sucesso: true, mensagem: "" });
    await api.treinarModelo();
    expect(fetchMock.mock.calls[0][1]).toEqual({ method: "POST" });

    responder({ sucesso: true, status: {} });
    await api.desconectarCamera();
    expect(fetchMock.mock.calls[1][0]).toBe(`${API_BASE_URL}/api/camera/desconectar`);
  });

  it("limites padrão de logs recentes e exceções", async () => {
    responder([]);
    responder([]);
    await api.getLogsRecentes();
    await api.getExcecoes();
    expect(fetchMock.mock.calls[0][0]).toContain("/api/logs/recentes?limite=15");
    expect(fetchMock.mock.calls[1][0]).toContain("/api/logs/excecoes?limite=15");
  });
});
