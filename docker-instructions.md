# AcompanhAR - Sistema de Coleta de Dados de Homecare

Sistema integrado para coleta de dados de visitas domiciliares via WhatsApp com processamento automático usando Gemini AI.

## 🏗️ Arquitetura

- **WhatsApp Monitor** (Node.js): Monitora mensagens do WhatsApp e coleta dados
- **API Gateway** (FastAPI/Python): Processa dados com Gemini AI
- **Docker**: Containerização completa do sistema

## 🚀 Configuração e Execução

### 1. Preparar o Ambiente

```bash
# Clone ou crie os arquivos do projeto
mkdir acompanhar-system
cd acompanhar-system

# Crie o arquivo .env baseado no .env.example
cp .env.example .env
```

### 2. Configurar Variáveis de Ambiente

Edite o arquivo `.env`:

```bash
GEMINI_API_KEY=sua_chave_do_gemini_aqui
BACKEND_URL=http://localhost:8000
NODE_ENV=production
PYTHON_ENV=production
```

### 3. Executar com Docker Compose

```bash
# Construir e executar
docker-compose up --build

# Ou executar em background
docker-compose up -d --build
```

### 4. Conectar o WhatsApp

1. Após iniciar, um QR code aparecerá no terminal
2. Escaneie o QR code com o WhatsApp Web
3. O sistema estará pronto para receber mensagens

## 📱 Como Usar

### Fluxo do Usuário

1. **Início**: Usuário envia qualquer mensagem para o número conectado
2. **Autenticação**: Sistema solicita PIN de entrada
3. **Coleta**: Usuário envia dados (áudios, imagens, textos)
4. **Finalização**: Usuário digita "0" para processar
5. **Resultado**: Sistema retorna resumo da visita

### Tipos de Dados Suportados

- 🎵 **Áudios**: Gravações de voz (qualquer formato)
- 📷 **Imagens**: Fotos de documentos, exames, etc.
- 📄 **Documentos**: PDFs, arquivos de texto
- 💬 **Textos**: Mensagens diretas no chat

## 🏥 Dados Extraídos

O sistema extrai automaticamente:

- **Estado do Paciente**: Condição geral
- **Sinais Vitais**: PA, FC, Temperatura, SpO2
- **Medicamentos**: Em uso e administrados
- **Materiais**: Utilizados na visita
- **Intervenções**: Procedimentos realizados
- **Recomendações**: Orientações médicas
- **Observações**: Notas importantes

## 📊 APIs Disponíveis

Com o sistema rodando:

- **Documentação**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health
- **Listar Relatórios**: http://localhost:8000/reports/list
- **Ver Relatório**: http://localhost:8000/reports/{filename}

## 🗂️ Estrutura de Arquivos

```
acompanhar-system/
├── Dockerfile
├── docker-compose.yml
├── run_services.sh
├── .env
├── main.py                 # API FastAPI
├── whatsapp_monitor.js     # Monitor WhatsApp
├── package.json
├── requirements.txt
├── messages/               # Mensagens salvas
├── audio_files/           # Áudios recebidos
├── media_files/           # Imagens e documentos
├── results/               # Relatórios processados
└── logs/                  # Logs do sistema
```

## 🔧 Comandos Úteis

### Docker

```bash
# Ver logs em tempo real
docker-compose logs -f

# Parar o sistema
docker-compose down

# Reiniciar apenas um serviço
docker-compose restart acompanhar-app

# Acessar o container
docker-compose exec acompanhar-app bash
```

### Limpeza

```bash
# Remover containers parados
docker-compose down --volumes

# Limpar dados (cuidado!)
docker system prune -a
```

## 🛠️ Desenvolvimento

### Executar Localmente (sem Docker)

```bash
# Instalar dependências Node.js
npm install

# Instalar dependências Python
pip install -r requirements.txt

# Executar API
python main.py

# Em outro terminal, executar WhatsApp monitor
node whatsapp_monitor.js
```

### Logs e Debug

```bash
# Ver logs da API
tail -f logs/api.log

# Debug do WhatsApp monitor
NODE_ENV=development node whatsapp_monitor.js
```

## ⚠️ Importantes

1. **Chave Gemini**: Obrigatória para funcionamento
2. **FFmpeg**: Incluído no Docker para conversão de áudio
3. **Persistência**: Dados salvos em volumes Docker
4. **Sessão WhatsApp**: Mantida entre reinicializações

## 🔐 Segurança

- Não compartilhe sua chave do Gemini
- Use PINs seguros em produção
- Monitore logs regularmente
- Faça backup dos dados importantes

## 📞 Suporte

Para problemas ou dúvidas:

1. Verifique os logs: `docker-compose logs`
2. Confirme as variáveis de ambiente
3. Teste a conectividade com a API Gemini
4. Reinicie o sistema se necessário