import type { CapturaDesconhecida, LogAcesso, Usuario } from "@/services/api";

export function criarLog(sobrescrever: Partial<LogAcesso> = {}): LogAcesso {
  return {
    id: 1,
    data_hora: "2026-03-10T14:32:00",
    usuario_id: 0,
    usuario_nome: "Ana Souza",
    status: "authorized",
    confianca: 0.7,
    distancia_lbph: 30.1,
    foto_path: null,
    ...sobrescrever,
  };
}

export function criarUsuario(sobrescrever: Partial<Usuario> = {}): Usuario {
  return {
    id: 0,
    nome: "Ana Souza",
    data_cadastro: "2026-03-01T09:00:00",
    status: "ativo",
    ultima_entrada: null,
    total_acessos: 0,
    ...sobrescrever,
  };
}

export function criarCaptura(sobrescrever: Partial<CapturaDesconhecida> = {}): CapturaDesconhecida {
  return { id: 7, data_hora: "2026-03-10T14:32:00", caminho_foto: "/static/desconhecidos/x.jpg", resolvida: 0, ...sobrescrever };
}
