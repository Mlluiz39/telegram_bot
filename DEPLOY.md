# Guia de Deploy - Oracle Cloud (Linux)

Embora não seja **estritamente obrigatório** usar `venv`, é **altamente recomendado** para evitar conflitos com as bibliotecas do sistema operacional da Oracle Cloud (que muitas vezes depende de versões específicas do Python).

## 1. Preparando o Servidor

Conecte-se à sua instância via SSH e atualize o sistema:
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install python3-pip python3-venv git -y
```

## 2. Configurando o Projeto

Clone seu repositório (ou copie os arquivos):
```bash
git clone https://github.com/seu-usuario/telegram_bot.git
cd telegram_bot
```

Crie e ative o ambiente virtual:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

Instale as dependências:
```bash
pip install -r requirements.txt
```

**Importante:** Crie o arquivo `.env` no servidor com suas credenciais de produção:
```bash
nano .env
# Cole o conteúdo do .env e salve (Ctrl+O, Enter, Ctrl+X)
```

## 3. Rodando em Segundo Plano (Modo Produção)

Para que o bot não pare de rodar quando você fechar o terminal, use o **Systemd**.

1. Crie um arquivo de serviço:
```bash
sudo nano /etc/systemd/system/telegram_bot.service
```

2. Cole o seguinte conteúdo (ajuste o usuário e caminhos conforme necessário):
```ini
[Unit]
Description=Telegram Bot Service
After=network.target

[Service]
# Substitua 'ubuntu' pelo seu usuário da Oracle Cloud (geralmente ubuntu ou opc)
User=ubuntu
WorkingDirectory=/home/ubuntu/telegram_bot
# Caminho para o python DENTRO do venv
ExecStart=/home/ubuntu/telegram_bot/.venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

3. Ative e inicie o serviço:
```bash
sudo systemctl daemon-reload
sudo systemctl enable telegram_bot
sudo systemctl start telegram_bot
```

## 4. Comandos Úteis

- **Ver status:** `sudo systemctl status telegram_bot`
- **Ver logs:** `journalctl -u telegram_bot -f`
- **Parar:** `sudo systemctl stop telegram_bot`
- **Reiniciar:** `sudo systemctl restart telegram_bot`
