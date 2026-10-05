export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";

export interface LogAcesso {
  id: number;
  data_hora: string;
  usuario_id: number | null;
  usuario_nome: string | null;
  status: "authorized" | "denied" | "revoked" | "no_face_detected" | string;
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

export const api = {
  async getStatus(): Promise<StatusSistema> {
    const res = await fetch(`${API_BASE_URL}/api/status`);
    if (!res.ok) throw new Error("Falha ao obter status do sistema");
    return res.json();
  },

  async getLogs(params?: {
    usuario?: string;
    status?: string;
    data_inicio?: string;
    data_fim?: string;
    limite?: number;
  }): Promise<LogAcesso[]> {
    const query = new URLSearchParams();
    if (params?.usuario) query.append("usuario", params.usuario);
    if (params?.status) query.append("status", params.status);
    if (params?.data_inicio) query.append("data_inicio", params.data_inicio);
    if (params?.data_fim) query.append("data_fim", params.data_fim);
    if (params?.limite) query.append("limite", String(params.limite));

    const res = await fetch(`${API_BASE_URL}/api/logs?${query.toString()}`);
    if (!res.ok) throw new Error("Falha ao obter logs");
    return res.json();
  },

  async getLogsRecentes(limite = 15): Promise<LogAcesso[]> {
    const res = await fetch(`${API_BASE_URL}/api/logs/recentes?limite=${limite}`);
    if (!res.ok) throw new Error("Falha ao obter logs recentes");
    return res.json();
  },

  async getExcecoes(limite = 15): Promise<LogAcesso[]> {
    const res = await fetch(`${API_BASE_URL}/api/logs/excecoes?limite=${limite}`);
    if (!res.ok) throw new Error("Falha ao obter exceções");
    return res.json();
  },

  async getUsuarios(): Promise<Usuario[]> {
    const res = await fetch(`${API_BASE_URL}/api/usuarios`);
    if (!res.ok) throw new Error("Falha ao obter usuários");
    return res.json();
  },

  async updateUsuarioStatus(usuarioId: number, status: "ativo" | "revogado"): Promise<{ sucesso: boolean }> {
    const res = await fetch(`${API_BASE_URL}/api/usuarios/${usuarioId}/status`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    });
    if (!res.ok) throw new Error("Falha ao atualizar status");
    return res.json();
  },

  async getCapturasDesconhecidas(): Promise<CapturaDesconhecida[]> {
    const res = await fetch(`${API_BASE_URL}/api/capturas-desconhecidas`);
    if (!res.ok) throw new Error("Falha ao obter capturas");
    return res.json();
  },

  async vincularCaptura(capturaId: number, nomePessoa: string): Promise<{ sucesso: boolean; mensagem: string }> {
    const res = await fetch(`${API_BASE_URL}/api/vincular-captura`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ captura_id: capturaId, nome_pessoa: nomePessoa }),
    });
    if (!res.ok) throw new Error("Falha ao vincular captura");
    return res.json();
  },

  async treinarModelo(): Promise<{ sucesso: boolean; mensagem: string }> {
    const res = await fetch(`${API_BASE_URL}/api/treinar`, {
      method: "POST",
    });
    if (!res.ok) throw new Error("Falha ao disparar treino");
    return res.json();
  },

  async getEstatisticas(): Promise<Estatisticas> {
    const res = await fetch(`${API_BASE_URL}/api/estatisticas`);
    if (!res.ok) throw new Error("Falha ao obter estatísticas");
    return res.json();
  },

  async simularLeitura(tipo: "autorizado" | "negado" | "revogado", nome = "Marina Costa"): Promise<{ sucesso: boolean }> {
    const res = await fetch(`${API_BASE_URL}/api/simular-leitura`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tipo, nome }),
    });
    if (!res.ok) throw new Error("Falha ao simular leitura");
    return res.json();
  },

  async conectarCamera(url: string): Promise<{ sucesso: boolean; status: { conectado: boolean; url: string; fps: number } }> {
    const res = await fetch(`${API_BASE_URL}/api/camera/conectar`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
    if (!res.ok) throw new Error("Falha ao conectar câmera");
    return res.json();
  },

  async desconectarCamera(): Promise<{ sucesso: boolean; status: { conectado: boolean } }> {
    const res = await fetch(`${API_BASE_URL}/api/camera/desconectar`, {
      method: "POST",
    });
    if (!res.ok) throw new Error("Falha ao desconectar câmera");
    return res.json();
  },

  async getCameraInfo(): Promise<{ conectado: boolean; url: string | null; fps: number; ultimo_frame_ts: string | null }> {
    const res = await fetch(`${API_BASE_URL}/api/camera/info`);
    if (!res.ok) throw new Error("Falha ao obter info da câmera");
    return res.json();
  },
};

