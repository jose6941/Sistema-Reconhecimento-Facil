# Sistema de Reconhecimento Facial de Baixo Custo para Controle de Acesso com ESP32-CAM

> **Trabalho de Conclusão de Curso (TCC)** — Instituto Federal de Educação, Ciência e Tecnologia de São Paulo (IFSP), Câmpus Birigui.

---

## 1. Visão Geral e Contexto Acadêmico

Este projeto apresenta uma solução completa de controle de acesso físico baseada em reconhecimento facial biométrico, orientada a restrições de custo e eficiência computacional. O sistema utiliza o microcontrolador **ESP32-CAM (sensor OV2640)** como nó de captura em borda (*edge sensing*), articulado a uma infraestrutura de processamento local em **Python** (detecção via *Haar Cascade* e classificação por *LBPH - Local Binary Patterns Histograms*) e uma interface web moderna em **Next.js** para monitoramento em tempo real, auditoria e administração de usuários.

### Métricas e Parâmetros de Avaliação do TCC
* **Classificador Biométrico**: LBPH (*OpenCV Face Recognizer*).
* **Limiar de Distância Qui-Quadrado (Threshold)**: Calibrado em `65.0` (distâncias inferiores indicam correspondência biométrica positiva).
* **FAR (False Acceptance Rate - Taxa de Falsa Aceitação)**: ~1,8% (calibrada no modelo).
* **FRR (False Rejection Rate - Taxa de Falsa Rejeição)**: ~4,3% (calibrada no modelo).
* **Resolução de Captura**: VGA (640×480 px), balanceada para precisão dos classificadores e vazão de rede.

---

## 2. Arquitetura do Sistema

A solução divide-se em três camadas interdependentes:

![Diagrama de Arquitetura e Fluxo de Comunicação HTTP](docs/arquitetura_fluxo_http.jpg)


1. **Camada de Captura (Edge - ESP32-CAM)**:
   - Módulo com sensor OV2640 calibrado (resolução VGA 640×480, ganho balanceado, algoritmo AEC2 e supressão de ruído térmico/pixels defeituosos);
   - Transmissão contínua do fluxo de vídeo MJPEG via `HTTP GET /stream` ou envio de quadros sob demanda via `HTTP POST multipart/form-data (/reconhecer)`.

2. **Camada de Processamento & Persistência (Backend - Python/Flask)**:
   - Pipeline de visão computacional: pré-processamento (escala de cinza, equalização de histograma, filtro Gaussiano), detecção por *Haar Cascade* e classificação biométrica via *LBPH* com ROI normalizada para 200×200 px;
   - Lógica de decisão de acesso por limiar de distância qui-quadrado ($\le 65.0$) com filtro temporal de *debounce* (4s) para evitar registros redundantes;
   - Notificações instantâneas e reativas para os clientes web via *Server-Sent Events* (`SSE /api/eventos`);
   - Persistência relacional e auditoria em SQLite (`acessos.db`), gerindo permissões de usuários (`ativo` / `revogado`), histórico completo e capturas pendentes de identificação.

3. **Camada de Apresentação (Frontend - Next.js 16 / React 19)**:
   - Painel administrativo moderno construído sobre o App Router e estilizado com Tailwind CSS;
   - **Ao Vivo**: Exibe o stream com *bounding boxes*, consome eventos via SSE em tempo real e disponibiliza o controle de simulação acadêmica;
   - **Pessoas**: Gestão cadastral de identidades, revogação/concessão de permissões, catálogo de capturas desconhecidas com vinculação e retreino automático em background (`POST /api/treinar`);
   - **Histórico**: Auditoria e consulta com filtros multicritério via API REST (`GET /api/logs`), fotos das tentativas e métricas biométricas consolidadas (FAR e FRR).

---

## 3. Estrutura do Diretório

```plaintext
├── CameraWebServer/             # Firmware C++/Arduino para o microcontrolador ESP32-CAM
│   ├── CameraWebServer.ino      # Sketch principal com calibração do sensor OV2640
│   ├── app_httpd.cpp            # Servidor HTTP embarcado (endpoints /stream e /capture)
│   ├── board_config.h           # Seleção do modelo da placa de desenvolvimento
│   └── camera_pins.h            # Mapeamento dos pinos GPIO da câmera
├── dataset/                     # Diretórios com imagens de treino agrupadas por pessoa
├── docs/                        # Documentação técnica e diagramas do projeto
│   └── arquitetura_fluxo_http.jpg # Diagrama visual de arquitetura e fluxo HTTP
├── frontend/                    # Painel Web Administrativo (Next.js 16, React 19, Tailwind)
│   ├── src/app/                 # Rotas e páginas (Ao Vivo, Pessoas, Histórico)
│   ├── src/components/          # Componentes reativos do painel
│   └── src/services/            # Clientes de comunicação com a API REST e SSE
├── static/                      # Recursos estáticos servidos pelo backend
│   ├── acessos/                 # Recortes faciais de acessos registrados
│   └── desconhecidos/           # Capturas de tentativas não identificadas
├── acessos.db                   # Banco de dados SQLite de auditoria e usuários
├── banco_dados.py               # Camada de persistência e consultas analíticas
├── capturar_dataset.py          # Utilitário CLI para captura e composição de dataset
├── iniciar_sistema.bat          # Script de inicialização unificada (Windows)
├── modelo_lbph.yml              # Modelo serializado do classificador treinado
├── labels.json                  # Mapeamento dos identificadores de classe para nomes
├── requirements.txt             # Dependências de pacotes Python
└── servidor_reconhecimento.py   # Servidor central (Pipeline OpenCV + API Flask)
```

---

## 4. Requisitos de Ambiente

* **Sistema Operacional**: Windows 10/11 ou Linux.
* **Python**: Versão 3.10 ou superior.
* **Node.js**: Versão 18.x ou superior (com gerenciador `npm`).
* **Arduino IDE**: Com suporte a placas ESP32 instalado (se for regravar o módulo físico).
* **Hardware (Opcional)**: Módulo ESP32-CAM AI-Thinker alimentado a 5V/2A. Na ausência do hardware, o sistema conta com modo de **webcam USB** e **simulador acadêmico integrado**.

---

## 5. Procedimento de Instalação e Configuração

### 5.1. Configuração do Backend (Python)

1. No terminal do diretório raiz do projeto, crie e ative um ambiente virtual:
   ```bash
   python -m venv venv
   # No Windows (PowerShell/CMD):
   .\venv\Scripts\activate
   # No Linux/macOS:
   source venv/bin/activate
   ```

2. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```

### 5.2. Configuração do Frontend (Next.js)

1. Acesse o subdiretório do frontend:
   ```bash
   cd frontend
   ```

2. Instale os módulos Node:
   ```bash
   npm install
   cd ..
   ```

### 5.3. Configuração do ESP32-CAM (Opcional - Gravação de Firmware)

1. Abra o arquivo `CameraWebServer/CameraWebServer.ino` na Arduino IDE.
2. Defina as credenciais da rede Wi-Fi local:
   ```cpp
   const char *ssid = "NOME_DA_SUA_REDE";
   const char *password = "SENHA_DA_SUA_REDE";
   ```
3. No menu **Tools > Board**, selecione **AI Thinker ESP32-CAM**.
4. Habilite a opção **PSRAM: Enabled** e grave o código no microcontrolador via módulo FTDI (GPIO 0 conectado ao GND no momento do boot).
5. Abra o monitor serial (115200 bps) para obter o endereço IP atribuído (ex.: `http://192.168.0.55`).

---

## 6. Operação do Sistema

### 6.1. Inicialização Integrada

Execute o script unificado para subir ambos os serviços simultaneamente:
```bat
.\iniciar_sistema.bat
```
O script iniciará:
- **Backend Flask & API**: [http://localhost:5000](http://localhost:5000)
- **Painel Administrativo Web**: [http://localhost:3000](http://localhost:3000)

### 6.2. Inicialização Manual por Terminais

* **Terminal 1 (Backend)**:
  ```bash
  .\venv\Scripts\python.exe servidor_reconhecimento.py
  # Ou com conexão automática ao stream do ESP32:
  .\venv\Scripts\python.exe servidor_reconhecimento.py --esp32-url http://192.168.0.55
  ```

* **Terminal 2 (Frontend)**:
  ```bash
  cd frontend
  npm run dev
  ```

---

## 7. Fluxos Operacionais e Funcionalidades

### 7.1. Coleta de Dataset e Treinamento

1. **Captura via Utilitário CLI**:
   Para registrar um novo indivíduo com auxílio de webcam ou do próprio ESP32-CAM (meta recomendada: 30 a 50 imagens com variação de pose e iluminação):
   ```bash
   # Utilizando webcam USB local:
   python capturar_dataset.py --pessoa "Fulano de Tal" --meta 40

   # Utilizando o módulo ESP32-CAM:
   python capturar_dataset.py --pessoa "Fulano de Tal" --esp32-url http://192.168.0.55 --meta 40
   ```

2. **Treinamento do Modelo**:
   O treinamento pode ser disparado via linha de comando ou diretamente pela interface web (Aba Pessoas > Botão *Treinar Modelo*):
   ```bash
   python servidor_reconhecimento.py --train
   ```

### 7.2. Associação Dinâmica de Faces Não Cadastradas

Quando o sistema detecta um rosto com distância LBPH superior a 65.0, a requisição é classificada como `denied`. O recorte facial é salvo em `static/desconhecidos/` e listado no painel web na seção **"Capturas sem cadastro"**. Um operador pode vincular a foto a uma pessoa existente ou criar um novo usuário com um clique, disparando o retreinamento incremental automático em segundo plano.

### 7.3. Revogação Instantânea de Acessos

Mesmo que o rosto esteja presente no modelo biométrico treinado, o status do usuário na tabela `usuarios` pode ser alterado para `revogado` através do painel. Nesses casos, o pipeline intercepta a autorização e classifica a tentativa como `revoked`, bloqueando a entrada e registrando a ocorrência no histórico de exceções.

### 7.4. Modo Simulação para Apresentações de Banca

Para mitigar imprevistos de conectividade física ou ausência de iluminação adequada no momento da apresentação acadêmica do TCC, o sistema conta com a funcionalidade de simulação integrada:
- Acessível diretamente pelo botão **"Simular Acesso"** no cabeçalho do painel web;
- Dispara cenários de teste controlados (*Acesso Autorizado*, *Acesso Negado/Desconhecido* e *Acesso Revogado*);
- Valida o ciclo completo de persistência, auditoria e reatividade visual via SSE sem necessidade de acionamento do sensor óptico.

---

## 8. Principais Rotas da API REST

| Método | Endpoint | Finalidade |
| :--- | :--- | :--- |
| `POST` | `/reconhecer` | Processa payload de imagem (multipart) enviado pelo ESP32-CAM |
| `GET` | `/saude` | Verificação de disponibilidade e status do modelo |
| `GET` | `/api/status` | Estado global da infraestrutura e métricas de conexão |
| `GET` | `/api/eventos` | Stream de Server-Sent Events (SSE) para atualização em tempo real |
| `GET` | `/api/logs` | Consulta ao histórico de auditoria com filtros |
| `GET` | `/api/usuarios` | Listagem de usuários, fotos e status atual |
| `PATCH`| `/api/usuarios/<id>/status`| Atualização de permissão (`ativo` / `revogado`) |
| `POST` | `/api/treinar` | Aciona o treinamento em segundo plano |
| `POST` | `/api/vincular-captura` | Vincula captura desconhecida a uma pasta do dataset |
| `POST` | `/api/camera/conectar` | Conecta o worker em background ao fluxo de vídeo do ESP32 |
| `POST` | `/api/simular-leitura` | Gera leitura simulada para testes e bancas |

---

## 9. Licença e Créditos

Trabalho desenvolvido no âmbito do Trabalho de Conclusão de Curso (TCC) do **IFSP Câmpus Birigui**.
Uso destinado a fins acadêmicos, de pesquisa e controle de acesso biométrico de baixo custo.
