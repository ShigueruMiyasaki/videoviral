# VideoViral

Painel para montar cortes 9:16 com reação em tela dividida. Na sua máquina ele abre em `http://127.0.0.1:8000`. Na VPS ele sobe com Docker a partir deste repositório.

O arquivo `.env` não entra no Git. Chaves de API e a senha do painel ficam só na máquina que executa.

## Publicar na VPS a partir do GitHub

Na VPS, como root:

```bash
git clone https://github.com/SEU-USUARIO/videoviral.git
cd videoviral
bash deploy/vps-up.sh
```

O script instala o Docker se ele não existir, copia `.env.example` para `.env`, gera `DASHBOARD_PASSWORD` se estiver vazia e sobe o painel. Caddy escuta nas portas 80 e 443. A porta 8000 não fica aberta na internet.

Abra `http://IP-DA-VPS`. O usuário é `admin`. A senha aparece uma vez no final do script e fica gravada no `.env` da VPS.

Para HTTPS, o DNS do domínio precisa apontar para o IP antes de subir. Coloque no `.env` da VPS e rode o script de novo:

```bash
VIDEOVIRAL_DOMAIN=painel.seudominio.com
bash deploy/vps-up.sh
```

Depois preencha no mesmo `.env` as chaves que for usar (`YOUTUBE_API_KEY`, `GEMINI_API_KEY`, `OPENAI_API_KEY`, ElevenLabs, HeyGen). Sem essas chaves o painel e a simulação de roteiro funcionam. Transcrição real, voz e avatar pago não.

Repositório público: o `git clone` acima basta. Repositório privado: crie um token do GitHub com permissão só de leitura do código e clone com ele. Não coloque o token dentro do repositório.

```bash
git clone https://github.com/SEU-USUARIO/videoviral.git
# na hora de pedir senha, use o token no lugar da senha da conta
```

## Na máquina Windows

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python run_api.py
```

Abra `http://127.0.0.1:8000/setup`. Sem `DASHBOARD_PASSWORD`, o painel local não pede senha.

O guia das fases seguintes está em [DESENVOLVIMENTO.md](DESENVOLVIMENTO.md).
