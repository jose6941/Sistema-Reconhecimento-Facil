import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api, type StatusSistema } from "@/services/api";
import { criarLog } from "@/test/fabricas";
import { TabAoVivo } from "./TabAoVivo";

vi.mock("@/services/api", async (importOriginal) => {
  const real = await importOriginal<typeof import("@/services/api")>();
  return { ...real, api: { getCameraInfo: vi.fn(), conectarCamera: vi.fn(), desconectarCamera: vi.fn() } };
});

const SEM_CAMERA = { conectado: false, url: null, fps: 0, ultimo_frame_ts: null };

function statusDo(ultimo: Partial<StatusSistema["ultimo_reconhecimento"]> = {}, cameraId = "CAM-07 · Garagem"): StatusSistema {
  return {
    status: "online",
    modelo_carregado: true,
    total_identidades: 1,
    limiar_lbph: 65,
    camera_id: cameraId,
    ultimo_reconhecimento: {
      status: "idle",
      user: null,
      user_id: null,
      confidence: 0,
      data_hora: null,
      foto_url: null,
      camera_id: cameraId,
      ...ultimo,
    },
  };
}

beforeEach(() => {
  vi.mocked(api.getCameraInfo).mockReset().mockResolvedValue(SEM_CAMERA);
  vi.mocked(api.conectarCamera).mockReset().mockResolvedValue({ sucesso: true, status: SEM_CAMERA });
  vi.mocked(api.desconectarCamera).mockReset().mockResolvedValue({ sucesso: true, status: SEM_CAMERA });
  vi.spyOn(console, "error").mockImplementation(() => {});
});

describe("TabAoVivo", () => {
  it("usa o nome da câmera vindo do servidor e mostra 'Aguardando'", async () => {
    render(<TabAoVivo statusSistema={statusDo()} logs={[]} onRefresh={vi.fn()} />);
    expect(screen.getByText("CAM-07 · Garagem")).toBeInTheDocument();
    expect(screen.getByText("Aguardando")).toBeInTheDocument();
    expect(screen.getByText("Nenhuma entrada registrada hoje.")).toBeInTheDocument();
    await waitFor(() => expect(api.getCameraInfo).toHaveBeenCalled());
  });

  it("o quadro inicial não depende do relógio (evita erro de hidratação SSR)", async () => {
    render(<TabAoVivo statusSistema={statusDo()} logs={[]} onRefresh={vi.fn()} />);
    const imagem = screen.getByAltText("Feed da Câmera");
    expect(imagem).toHaveAttribute("src", expect.stringMatching(/ultimo-frame\?t=0$/));
    await waitFor(() => expect(api.getCameraInfo).toHaveBeenCalled());
  });

  it("sem dados do servidor usa o nome padrão", async () => {
    render(<TabAoVivo statusSistema={null} logs={[]} onRefresh={vi.fn()} />);
    expect(screen.getByText("CAM-01 · Portaria")).toBeInTheDocument();
    await waitFor(() => expect(api.getCameraInfo).toHaveBeenCalled());
  });

  it("mostra o último reconhecimento", async () => {
    const status = statusDo({ status: "authorized", user: "Ana Souza", confidence: 0.912, data_hora: "2026-03-10T14:32:00" });
    render(<TabAoVivo statusSistema={status} logs={[]} onRefresh={vi.fn()} />);
    expect(screen.getByText("Autorizado")).toBeInTheDocument();
    expect(screen.getByText(/Ana Souza · match 91.2%/)).toBeInTheDocument();
    await waitFor(() => expect(api.getCameraInfo).toHaveBeenCalled());
  });

  it("revogado aparece como 'Não autorizado'", async () => {
    const status = statusDo({ status: "revoked", user: "Bia", data_hora: "2026-03-10T14:32:00" });
    render(<TabAoVivo statusSistema={status} logs={[]} onRefresh={vi.fn()} />);
    expect(screen.getAllByText("Não autorizado").length).toBeGreaterThan(0);
    await waitFor(() => expect(api.getCameraInfo).toHaveBeenCalled());
  });

  it("lista as entradas sem inventar porcentagens", async () => {
    const logs = [
      criarLog({ id: 1, usuario_nome: "Ana", status: "authorized", confianca: 0 }),
      criarLog({ id: 2, usuario_nome: null, status: "denied", confianca: 0 }),
      criarLog({ id: 3, usuario_nome: "Bia", status: "revoked", confianca: 0.94 }),
    ];
    render(<TabAoVivo statusSistema={statusDo()} logs={logs} onRefresh={vi.fn()} />);

    expect(screen.getByText("Ana")).toBeInTheDocument();
    expect(screen.getByText("Desconhecido")).toBeInTheDocument();
    expect(screen.queryByText(/96%/)).not.toBeInTheDocument();
    expect(screen.getByText(/· 94%/)).toBeInTheDocument();
    expect(screen.getByText("Não registrado")).toBeInTheDocument();
    await waitFor(() => expect(api.getCameraInfo).toHaveBeenCalled());
  });

  it("conecta ao ESP32 informando o endereço", async () => {
    const user = userEvent.setup();
    render(<TabAoVivo statusSistema={statusDo()} logs={[]} onRefresh={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: /Conectar ESP32/ }));
    const campo = screen.getByLabelText(/Endereço IP/);
    await user.clear(campo);
    await user.type(campo, "  http://192.168.0.99  ");
    await user.click(screen.getByRole("button", { name: "Conectar Stream" }));

    expect(api.conectarCamera).toHaveBeenCalledWith("http://192.168.0.99");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("endereço recusado pelo servidor mostra erro e mantém o modal", async () => {
    vi.mocked(api.conectarCamera).mockRejectedValue(new Error("400"));
    const user = userEvent.setup();
    render(<TabAoVivo statusSistema={statusDo()} logs={[]} onRefresh={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: /Conectar ESP32/ }));
    await user.click(screen.getByRole("button", { name: "Conectar Stream" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/Endereço recusado/);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("campo vazio desabilita a conexão", async () => {
    const user = userEvent.setup();
    render(<TabAoVivo statusSistema={statusDo()} logs={[]} onRefresh={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: /Conectar ESP32/ }));
    await user.clear(screen.getByLabelText(/Endereço IP/));
    expect(screen.getByRole("button", { name: "Conectar Stream" })).toBeDisabled();
  });

  it("câmera conectada mostra FPS e permite desconectar", async () => {
    vi.mocked(api.getCameraInfo).mockResolvedValue({ conectado: true, url: "http://192.168.0.55/stream", fps: 12.5, ultimo_frame_ts: null });
    const user = userEvent.setup();
    render(<TabAoVivo statusSistema={statusDo()} logs={[]} onRefresh={vi.fn()} />);

    const pill = await screen.findByRole("button", { name: /12.5 FPS/ });
    await user.click(pill);
    expect(screen.getByLabelText(/Endereço IP/)).toHaveValue("http://192.168.0.55");
    await user.click(screen.getByRole("button", { name: "Desconectar" }));

    expect(api.desconectarCamera).toHaveBeenCalled();
  });

  it("backend fora do ar não quebra a aba", async () => {
    vi.mocked(api.getCameraInfo).mockRejectedValue(new Error("offline"));
    render(<TabAoVivo statusSistema={null} logs={[]} onRefresh={vi.fn()} />);
    await waitFor(() => expect(api.getCameraInfo).toHaveBeenCalled());
    expect(screen.getByText(/Conectar ESP32/)).toBeInTheDocument();
  });

  it("o botão de atualizar chama onRefresh", async () => {
    const onRefresh = vi.fn();
    const user = userEvent.setup();
    render(<TabAoVivo statusSistema={statusDo()} logs={[]} onRefresh={onRefresh} />);
    await user.click(screen.getByRole("button", { name: "Atualizar feed" }));
    expect(onRefresh).toHaveBeenCalled();
  });
});
