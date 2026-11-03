export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";

export interface LogAcesso {
  id: number;
  data_hora: string;
  usuario_id: number | null;
  usuario_nome: string | null;
  /** "authorized" | "denied" | "revoked" | "no_face_detected" | "error" */
  status: string;
  confianca: number;
  distancia_lbph: number | null;
  foto_path: string | null;
}

export interface Usuario {
  id: number;
  nome: string;
  data_cadastro: string;
  status: "ativo" | "revogado";
  ultima_entrada: string | null;
  total_acessos: number;
  total_fotos?: number;
}

export interface CapturaDesconhecida {
  id: number;
  data_hora: string;
  caminho_foto: string;
  resolvida: number;
  usuario_id?: number | null;
}

export interface Estatisticas {
  entradas_hoje: number;
  total_tentativas_hoje: number;
  excecoes_hoje: number;
  falsos_aceitos_pct: number;
  falsos_rejeitados_pct: number;
  total_usuarios: number;
  usuarios_ativos: number;
  usuarios_revogados: number;
  capturas_pendentes: number;
}

export interface StatusSistema {
  status: string;
  modelo_carregado: boolean;
  total_identidades: number;
  limiar_lbph: number;
  camera_id: string;
  ultimo_reconhecimento: {
    status: string;
    user: string | null;
    user_id: number | null;
    confidence: number;
    distance_lbph?: number | null;
    data_hora: string | null;
    foto_url: string | null;
    camera_id: string;
  };
}

export interface FiltrosLogs {
  usuario?: string;
  status?: string;
  data_inicio?: string;
  data_fim?: string;
  /** Só registros diferentes de "authorized". */
  excecoes?: boolean;
  limite?: number;
  offset?: number;
}

export interface InfoCamera {
  conectado: boolean;
  url: string | null;
  fps: number;
  ultimo_frame_ts: string | null;
}

/** Chama a API e converte respostas de erro em exceção com `mensagemErro`. */
async function requisitar<T>(caminho: string, mensagemErro: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${caminho}`, init);
  if (!res.ok) throw new Error(mensagemErro);
  return res.json();
}

function enviarJson(metodo: string, corpo?: unknown): RequestInit {
  if (corpo === undefined) return { method: metodo };
  return { method: metodo, headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo) };
}

export function montarQueryLogs(filtros: FiltrosLogs = {}): string {
  const query = new URLSearchParams();
  if (filtros.usuario) query.append("usuario", filtros.usuario);
  if (filtros.status) query.append("status", filtros.status);
  if (filtros.data_inicio) query.append("data_inicio", filtros.data_inicio);
  if (filtros.data_fim) query.append("data_fim", filtros.data_fim);
  if (filtros.excecoes) query.append("excecoes", "true");
  if (filtros.limite) query.append("limite", String(filtros.limite));
  if (filtros.offset) query.append("offset", String(filtros.offset));
  return query.toString();
}

export const api = {
  getStatus: () => requisitar<StatusSistema>("/api/status", "Falha ao obter status do sistema"),

  getLogs: (filtros?: FiltrosLogs) =>
    requisitar<LogAcesso[]>(`/api/logs?${montarQueryLogs(filtros)}`, "Falha ao obter logs"),

  getLogsRecentes: (limite = 15) =>
    requisitar<LogAcesso[]>(`/api/logs/recentes?limite=${limite}`, "Falha ao obter logs recentes"),

  getExcecoes: (limite = 15) =>
    requisitar<LogAcesso[]>(`/api/logs/excecoes?limite=${limite}`, "Falha ao obter exceções"),

  getUsuarios: () => requisitar<Usuario[]>("/api/usuarios", "Falha ao obter usuários"),

  updateUsuarioStatus: (usuarioId: number, status: "ativo" | "revogado") =>
    requisitar<{ sucesso: boolean }>(
      `/api/usuarios/${usuarioId}/status`,
      "Falha ao atualizar status",
      enviarJson("PATCH", { status }),
    ),

  getCapturasDesconhecidas: () =>
    requisitar<CapturaDesconhecida[]>("/api/capturas-desconhecidas", "Falha ao obter capturas"),

  vincularCaptura: (capturaId: number, nomePessoa: string) =>
    requisitar<{ sucesso: boolean; mensagem: string }>(
      "/api/vincular-captura",
      "Falha ao vincular captura",
      enviarJson("POST", { captura_id: capturaId, nome_pessoa: nomePessoa }),
    ),

  treinarModelo: () =>
    requisitar<{ sucesso: boolean; mensagem: string }>("/api/treinar", "Falha ao disparar treino", enviarJson("POST")),

  getEstatisticas: () => requisitar<Estatisticas>("/api/estatisticas", "Falha ao obter estatísticas"),

  simularLeitura: (tipo: "autorizado" | "negado" | "revogado", nome = "Marina Costa") =>
    requisitar<{ sucesso: boolean }>(
      "/api/simular-leitura",
      "Falha ao simular leitura",
      enviarJson("POST", { tipo, nome }),
    ),

  conectarCamera: (url: string) =>
    requisitar<{ sucesso: boolean; status: InfoCamera }>(
      "/api/camera/conectar",
      "Falha ao conectar câmera",
      enviarJson("POST", { url }),
    ),

  desconectarCamera: () =>
    requisitar<{ sucesso: boolean; status: InfoCamera }>(
      "/api/camera/desconectar",
      "Falha ao desconectar câmera",
      enviarJson("POST"),
    ),

  getCameraInfo: () => requisitar<InfoCamera>("/api/camera/info", "Falha ao obter info da câmera"),
};
