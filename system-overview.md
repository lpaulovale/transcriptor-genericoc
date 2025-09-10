# AcompanhAR - Sistema Multi-Container

## 🏗️ Arquitetura de 3 Containers

### Container A: `acompanhar-api` (FastAPI Backend)
- **Porta**: 8000
- **Função**: API principal para processamento de dados
- **Tecnologia**: Python + FastAPI + Gemini AI
- **Endpoints**:
  - `GET /` - Status da API
  - `GET /health` - Health check
  - `POST /extract/visit-report` - Processar dados da visita
  - `GET /reports/list` - Listar relatórios
  - `GET /reports/{filename}` - Ver relatório específico

### Container B: `acompanhar-whatsapp` (WhatsApp Monitor)
- **Porta**: 3000 (health check)
- **Função**: Monitor de mensagens WhatsApp
- **Tecnologia**: Node.js + WhatsApp Web.js + Puppeteer
- **Recursos**:
  - Autenticação via QR code
  - Sistema de PIN para usuários
  - Coleta multimodal (áudio, imagem, texto)
  - Comunicação com Container A

### Container C: `acompanhar-processor` (File Processor)
- **Porta**: 8001 (health check)
- **Função**: Processamento de arquivos em background
- **Tecnologia**: Python + FFmpeg + pydub
- **Recursos**:
  - Conversão de áudio para WAV
  - Otimização de arquivos
  - Monitoramento de diretório compartilhado

## 📊 Fluxo de Dados

```
WhatsApp User → Container B → Container A → Container C
     ↓              ↓              ↓              ↓
  Mensagem    Coleta Dados   Processa AI   Otimiza Files
     ↓              ↓              ↓              ↓
   PIN/Audio → Armazena Local → Gemini API → Converte WAV
     ↓              ↓              ↓              ↓
  Finaliza "0" → Envia para API → Gera JSON → Salva Result
```

## 🚀 Como Executar

### 1. Preparação
```bash
# Clone o projeto
git clone <repo> && cd acompanhar-system

# Configure variáveis
cp .env.example .env
# Edite .env com sua GEMINI_API_KEY
```

### 2. Execução Automática
```bash
# Tornar executável e executar
chmod +x start_system.sh
./start_system.sh
```

### 3. Execução Manual
```bash
# Construir e executar containers
docker-compose up --build

# Executar em background
docker-compose up -d --build
```

## 🔍 Monitoramento

### Health Checks
- **API**: `curl http://localhost:8000/health`
- **WhatsApp**: `curl http://localhost:3000/health`
- **Processor**: `curl http://localhost:8001/health`

### Logs
```bash
# Todos os containers
docker-compose logs -f

# Container específico
docker-compose logs -f acompanhar-api
docker-compose logs -f acompanhar-whatsapp
docker-compose logs -f acompanhar-processor
```

### Status dos Containers
```bash
docker-compose ps
```

## 📁 Estrutura de Volumes

```
acompanhar-system/
├── messages/           # Mensagens WhatsApp (Container B)
├── audio_files/        # Arquivos de áudio (B → C)
├── media_files/        # Imagens e documentos (B → A)
├── results/           # Relatórios processados (A)
├── logs/              # Logs do sistema (A, B, C)
└── shared_data/       # Comunicação entre containers
```

## 🔧 Comandos Úteis

### Docker
```bash
# Parar tudo
docker-compose down

# Rebuild específico
docker-compose up --build acompanhar-api

# Remover volumes (cuidado!)
docker-compose down --volumes

# Acessar container
docker exec -it acompanhar-api bash
docker exec -it acompanhar-whatsapp bash
docker exec -it acompanhar-processor bash
```

### Limpeza
```bash
# Limpar containers parados
docker system prune

# Limpar tudo (CUIDADO!)
docker system prune -a --volumes
```

## 🛡️ Segurança e Configuração

### Variáveis de Ambiente (.env)
```bash
GEMINI_API_KEY=sua_chave_aqui           # Obrigatório
BACKEND_URL=http://acompanhar-api:8000  # Comunicação interna
NODE_ENV=production
PYTHON_ENV=production
```

### Portas Expostas
- `8000`: API FastAPI (público)
- `3000`: WhatsApp Monitor health check
- `8001`: File Processor health check

### Volumes Persistentes
- `whatsapp_session`: Sessão WhatsApp (persiste login)
- `shared_data`: Comunicação entre containers
- Diretórios locais: `messages`, `audio_files`, `media_files`, `results`, `logs`

## 🔄 Fluxo de Uso da Aplicação

1. **Usuário inicia conversa** → WhatsApp Monitor (Container B)
2. **Sistema solicita PIN** → Usuário fornece PIN
3. **Coleta de dados** → Usuário envia áudios/fotos/textos
4. **Usuário digita "0"** → Finaliza coleta
5. **Processamento** → Container B → Container A (API + Gemini)
6. **Otimização de arquivos** → Container C processa arquivos
7. **Resultado** → JSON salvo em `/results` + resumo enviado ao usuário

## 📝 Logs e Debug

### Localizações dos Logs
- API: `logs/api.log`
- Processor: `logs/processor.log`
- WhatsApp: Output do container (docker logs)

### Troubleshooting
1. **QR Code não aparece**: Verificar logs do container WhatsApp
2. **API não responde**: Verificar health check e logs
3. **Áudio não processa**: Verificar container Processor
4. **Gemini falha**: Verificar GEMINI_API_KEY no .env

## 🎯 Benefícios da Arquitetura Multi-Container

- **Escalabilidade**: Cada serviço pode ser escalado independentemente
- **Manutenibilidade**: Separação clara de responsabilidades
- **Confiabilidade**: Falha em um container não afeta os outros
- **Desenvolvimento**: Equipes podem trabalhar em containers específicos
- **Performance**: Processamento paralelo otimizado