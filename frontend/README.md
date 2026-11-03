# Painel Web — Sistema de Reconhecimento Facial

Painel em **Next.js 16 / React 19 / Tailwind 4** que acompanha em tempo real o backend de reconhecimento facial (TCC IFSP Birigui). Requer **Node.js 20 ou superior**.

## Telas
- **Ao vivo** (`/`): último quadro processado, resultado do reconhecimento e registro de entradas (atualização por SSE).
- **Pessoas**: cadastrados, revogar/reativar, treinar o modelo e vincular rostos desconhecidos.
- **Histórico**: indicadores, exceções e auditoria com filtros (nome, status, exceções e período) consultados no servidor, com paginação.
- **Documentação** (`/documentacao`): features, regras de negócio e requisitos, com abas **Main** (versão atual) e **Log** (versões anteriores, adições em verde e remoções em vermelho).

## Configuração
Copie `.env.example` para `.env` e ajuste:

| Variável | Descrição |
| :--- | :--- |
| `NEXT_PUBLIC_API_URL` | URL do backend Flask (padrão `http://localhost:5000`). É embutida no build: reinicie o `dev` ou refaça o `build` ao alterar. |

## Comandos
```bash
npm install
npm run dev          # desenvolvimento em http://localhost:3000
npm run build        # build de produção
npm start            # serve o build
npm run lint         # ESLint
npm run typecheck    # TypeScript
npm test             # testes em modo watch (Vitest)
npm run test:run     # testes uma vez (CI)
npm run doc:nova-versao   # cria a próxima versão da documentação
```

## Estrutura (`src/`)
| Pasta | Conteúdo |
| :--- | :--- |
| `app/` | Rotas: `page.tsx` (painel), `documentacao/page.tsx`, layout e estilos globais. |
| `components/` | Telas (`TabAoVivo`, `TabPessoas`, `TabHistorico`, `DocumentacaoView`, `Header`) e peças reutilizáveis (`Modal`, `StatusBadge`, `TabButton`). |
| `lib/` | `formatadores`, `status` (rótulos e cores), `useDebounce` e `documentacao` (leitura das versões e diff). |
| `services/api.ts` | Cliente tipado da API do backend. |
| `content/documentacao/` | Uma versão da documentação por arquivo: `V####_AAAA-MM-DD.md`. |
| `test/` | Fábricas usadas pelos testes. |

## Documentação versionada
1. Rode `npm run doc:nova-versao`: cria a próxima versão (número +1, data de hoje) copiando a mais recente.
2. Edite o arquivo criado. Cada linha é um item (`#`, `##`, `###`, `- ` ou parágrafo; `**negrito**` e `` `código` `` são aceitos).
3. A aba **Main** passa a mostrar a nova versão e a aba **Log** mostra o que foi adicionado e removido em relação à anterior.
4. Após editar, faça um novo `npm run build` (a página é gerada no build).

Os testes em `lib/conteudo-documentacao.test.ts` conferem nomes, numeração sequencial e seções obrigatórias.
