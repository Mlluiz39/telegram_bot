# Medication Reminder Bot 💊

Este é um bot de Telegram desenvolvido em Python para ajudar pacientes a lembrarem de tomar seus medicamentos. Ele se integra ao Supabase para gerenciar horários, pacientes e histórico de medicamentos.

## ✨ Funcionalidades

- **Lembretes Automáticos**: Envia notificações no horário exato programado para o medicamento.
- **Sincronização Inteligente**: Gera automaticamente a agenda do dia e corrige falhas caso o bot fique offline por alguns minutos.
- **Registro de Status**: Botões interativos ("✅ Tomei" / "❌ Não Tomei") para registrar no banco de dados se o medicamento foi administrado.
- **Auto-Recuperação**: Verifica periodicamente (a cada 5 min) se há novos medicamentos ou se a agenda precisa ser recriada.

## 🛠️ Tecnologias

- [Python 3.12+](https://www.python.org/)
- [Python Telegram Bot](https://python-telegram-bot.org/)
- [Supabase](https://supabase.com/) (PostgreSQL)

## 🚀 Como Rodar Localmente

### 1. Pré-requisitos

Certifique-se de ter o Python e o Git instalados.

### 2. Instalação

Clone o repositório e entre na pasta:
```bash
git clone https://github.com/seu-usuario/telegram_bot.git
cd telegram_bot
```

Crie e ative um ambiente virtual:
```bash
# Linux/Mac
python3 -m venv .venv
source .venv/bin/activate

# Windows
python -m venv .venv
.venv\Scripts\activate
```

Instale as dependências:
```bash
pip install -r requirements.txt
```

### 3. Configuração

Renomeie o arquivo `.env.example` para `.env` e preencha as variáveis:
```ini
SUPABASE_URL="sua_url_do_supabase"
SUPABASE_SERVICE_KEY="sua_chave_service_role"
TELEGRAM_BOT_TOKEN="seu_token_do_botfather"
```

### 4. Execução

Rode o bot:
```bash
python main.py
```

## ☁️ Deploy em Produção

Para implantar este bot em um servidor (como Oracle Cloud, AWS, DigitalOcean), consulte o guia detalhado:

👉 **[Leia o Guia de Deploy (DEPLOY.md)](./DEPLOY.md)**

## 📂 Estrutura do Projeto

- `main.py`: Código principal do bot e agendador.
- `requirements.txt`: Lista de dependências Python.
- `DEPLOY.md`: Instruções para subir em produção.
- `inspect_db.py`, `debug_schedule.py`: Scripts auxiliares para depuração.

## 📝 Licença

Este projeto é de uso privado.
