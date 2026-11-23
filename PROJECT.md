# VideoViral — Dark Content Automation Platform

> Guia ativo da fase atual: [DESENVOLVIMENTO.md](DESENVOLVIMENTO.md). Este arquivo continua como checklist do que o MVP-1 já cobriu.

> Aplicativo automatizado de criação de conteúdo vertical (TikTok, YouTube Shorts, Reels).  
> Minera tendências → corta melhores momentos → avatar IA reage → distribui.

**Status geral:** `[~]` MVP-1 em progresso

### Entregas recentes (MVP-1 / MVP-2)
- [x] Estrutura base + `example_clip_flow.py`
- [x] CLI `run_miner.py` (YouTube Shorts + download)
- [x] HeyGen integrado (`avatar_gen.py`) + placeholder dev
- [x] API FastAPI + dashboard Kanban (`http://127.0.0.1:8000`)
- [x] Pipeline completo `full_pipeline.py` com fila de aprovação
- [x] `render_job.py` — etapas de render + barra de progresso no dashboard
- [x] Fallback heurístico de corte se LLM falhar
- [x] `--mock-transcribe` — pipeline sem OpenAI Whisper
- [x] `src/transcription.py` — Whisper API real (retry, compressão, idioma PT)
- [x] `test_whisper.py` — CLI de teste da transcrição
- [x] Dashboard v2 — coluna Falhou, progresso, preview do output, poll 2s

---

## Stack Tecnológica Recomendada

| Camada | Tecnologia | Motivo |
|--------|------------|--------|
| **Linguagem core** | Python 3.11+ | Ecossistema maduro para vídeo, IA e scraping |
| **Orquestração** | Celery + Redis | Filas baratas para jobs longos (transcrição, render) |
| **API / Dashboard** | FastAPI + React (Vite) | Painel de aprovação Kanban com baixo custo |
| **Banco principal** | PostgreSQL | Metadados, jobs, aprovações, A/B tests |
| **Cache / fila** | Redis | Rate limits de APIs, sessões, filas |
| **Armazenamento** | MinIO (S3-compatível) ou Cloudflare R2 | Vídeos intermediários e finais baratos |
| **Vídeo** | FFmpeg (via `ffmpeg-python`) | Corte, resize 9:16, composição, legendas |
| **Transcrição** | OpenAI Whisper API | Timestamps precisos, custo previsível |
| **LLM decisão** | Google Gemini 2.0 Flash / GPT-4o-mini | Hook/clímax, roteiro reação, títulos A/B |
| **Avatar lip-sync** | HeyGen API ou D-ID | Qualidade comercial, webhook async |
| **Voz** | ElevenLabs | Clonagem + TTS reativo ao roteiro |
| **Mineração YT** | YouTube Data API v3 | Shorts com filtros por nicho |
| **Mineração TT/IG** | Apify actors / RapidAPI (oficial limitado) | Sem API pública estável do TikTok |
| **Legendas burn-in** | FFmpeg `drawtext` + ASS/SRT estilizado | Karaoke sem SaaS caro |
| **Distribuição** | Webhooks (Make/Zapier) + Buffer API (futuro) | Postagem agendada desacoplada |
| **Infra barata** | Docker Compose local → Railway/Fly.io workers | GPU só no render se necessário |

---

## Estrutura de Diretórios

```
videoviral/
├── PROJECT.md                 # Este arquivo (checklist + commits)
├── requirements.txt
├── .env.example
├── docker-compose.yml
├── config/
│   └── settings.py
├── src/
│   ├── __init__.py
│   ├── miner.py               # Pilar 1: mineração viral
│   ├── clipper.py             # Pilar 2: transcrição + corte IA
│   ├── bypass.py              # Evasão conteúdo reutilizado
│   ├── subtitles.py           # Legendas dinâmicas karaoke
│   ├── avatar_gen.py          # Pilar 3: avatar + voz
│   ├── renderer.py            # Composição final 9:16
│   ├── distribution.py        # Pilar 4: export + webhooks
│   ├── sentiment.py           # Análise sentimento pré-aprovação
│   ├── ab_testing.py          # Títulos, tags, thumbnails
│   ├── models/                # Schemas Pydantic / ORM
│   └── pipeline/
│       └── example_clip_flow.py  # Exemplo integrado
├── api/
│   ├── main.py                # FastAPI — dashboard aprovação
│   └── routes/
│       ├── approval.py
│       └── jobs.py
├── workers/
│   └── tasks.py               # Celery tasks
├── frontend/                  # (fase 2) React Kanban
├── storage/
│   ├── raw/                   # Vídeos baixados
│   ├── clips/                 # Cortes intermediários
│   └── output/                # MP4 finais 1080x1920
└── tests/
```

---

## CHECKLIST — PILAR 1: Mineração de Vídeos Virais

### Configuração & APIs
- [ ] Criar projeto Google Cloud e habilitar YouTube Data API v3
- [ ] Configurar `YOUTUBE_API_KEY` no `.env`
- [ ] Definir quotas diárias e cache de respostas (Redis, TTL 1h)
- [ ] Pesquisar e escolher provider TikTok (Apify / RapidAPI / manual RSS)
- [ ] Pesquisar provider Instagram Reels (Meta Graph API ou scraper terceiro)
- [ ] Documentar limites legais/ToS de cada fonte

### Módulo `miner.py`
- [ ] Implementar busca YouTube Shorts (`videoDuration=short`, `order=viewCount`)
- [ ] Filtrar vídeos com pico nas últimas 24h (views/hora vs média do canal)
- [ ] Calcular score de engajamento: `(likes + comments*3) / views`
- [ ] Filtro por nicho via keywords + categorias (`finance`, `podcast`, `curiosidades`, `games`)
- [ ] Persistir candidatos em PostgreSQL (`viral_candidates`)
- [ ] Download do vídeo via `yt-dlp` para `storage/raw/`
- [ ] Deduplicar por `video_id` e hash do arquivo
- [ ] Agendar varredura periódica (Celery beat, ex: a cada 6h)
- [ ] Logs estruturados (JSON) para auditoria

### Testes Pilar 1
- [ ] Teste unitário: cálculo de score de engajamento
- [ ] Teste integração: mock YouTube API retorna 10 Shorts
- [ ] Teste: filtro por nicho "finanças" exclui outros

---

## CHECKLIST — PILAR 2: Edição Inteligente e Clipper

### Transcrição
- [ ] Extrair áudio do MP4 com FFmpeg (`-vn -acodec pcm_s16le`)
- [ ] Enviar para OpenAI Whisper API (`verbose_json` com timestamps)
- [ ] Salvar transcrição segmentada em JSON (`storage/clips/{id}_transcript.json`)

### Decisão IA (hook + clímax)
- [ ] Prompt estruturado para LLM retornar JSON: `{start, end, hook_text, climax_reason}`
- [ ] Validar duração do corte ≤ 60 segundos
- [ ] Fallback: se LLM falhar, usar segmento de maior densidade de palavras/min
- [ ] Implementar em `clipper.py` → `find_best_clip(transcript, max_duration=60)`

### Corte físico
- [ ] FFmpeg: `-ss {start} -to {end} -c copy` ou re-encode se necessário
- [ ] Resize/crop para 9:16 (1080x1920) com `scale` + `crop` center
- [ ] Normalizar áudio (-14 LUFS aproximado para redes sociais)
- [ ] Salvar em `storage/clips/{id}_clip.mp4`

### Testes Pilar 2
- [ ] Teste: transcrição mock → LLM mock → timestamps válidos
- [ ] Teste: vídeo 16:9 vira 9:16 sem distorção
- [ ] Teste: corte > 60s é rejeitado/truncado

---

## CHECKLIST — PILAR 3: Avatar de IA Reacionário

### Geração de roteiro
- [ ] LLM gera comentário 15–40 palavras (tom por nicho: sarcástico/informativo/humor)
- [ ] Incluir contexto: hook detectado + resumo do clipe
- [ ] Salvar roteiro em DB aguardando aprovação humana

### Voz (ElevenLabs)
- [ ] Configurar `ELEVENLABS_API_KEY` e `voice_id` por persona
- [ ] Gerar MP3 da reação
- [ ] Cache de áudios por hash do texto

### Avatar (HeyGen / D-ID)
- [ ] Upload áudio ou TTS integrado na API do provider
- [ ] Polling/webhook até vídeo do avatar pronto
- [ ] Baixar MP4 do avatar (fundo transparente ou chroma key se disponível)

### Layout final (`renderer.py`)
- [ ] Modo A: clipe fullscreen + avatar circular canto inferior direito
- [ ] Modo B: split screen estilo Duet (50/50)
- [ ] Modo C: PiP com borda e sombra
- [ ] Export 1080x1920 @ 30fps (opcional 60fps)

### Testes Pilar 3
- [ ] Mock APIs avatar/voz
- [ ] Composição FFmpeg gera MP4 válido
- [ ] Duração final = max(clipe, avatar) com sync

---

## CHECKLIST — PILAR 4: Distribuição Automática

- [ ] Export final: H.264, AAC, 1080x1920, `-crf 23`, `-preset medium`
- [ ] Metadados sidecar JSON (título, tags, nicho, job_id)
- [ ] Webhook POST para Make/Zapier (`DISTRIBUTION_WEBHOOK_URL`)
- [ ] Payload padronizado: `{video_url, title, tags[], thumbnail_url, platforms[]}`
- [ ] Fila de retry com backoff exponencial
- [ ] (Futuro) Integração Buffer / Later / API nativa TikTok Business
- [ ] (Futuro) Upload direto YouTube Shorts via Data API

### Testes Pilar 4
- [ ] Webhook mock recebe payload correto
- [ ] Arquivo final passa validação `ffprobe`

---

## CHECKLIST — FUNÇÕES DE ALTO VALOR

### 1. Bypass Conteúdo Reutilizado (`bypass.py`)
- [ ] Velocidade vídeo 1.02x (`setpts=0.98*PTS`)
- [ ] Ajuste saturação/brilho sutil (`eq=saturation=1.05:brightness=0.02`)
- [ ] Ruído de áudio imperceptível (`anoisesrc` mixado -35dB)
- [ ] Zoom dinâmico keyframes nos primeiros 3s (`zoompan` filter)
- [ ] Espelhamento horizontal opcional (flag por nicho)
- [ ] Pipeline: clip → bypass → legendas → composição

### 2. Legendas Dinâmicas (`subtitles.py`)
- [ ] Gerar ASS com estilo TikTok (fonte bold, outline, sombra)
- [ ] Efeito karaoke: palavra atual em cor destaque (`\kf` tags ASS)
- [ ] Mesclar legendas do clipe original + reação do avatar
- [ ] Burn-in via FFmpeg `ass` filter
- [ ] Presets de fonte por nicho (config YAML)

### 3. Dashboard Aprovação Humana (`api/`)
- [ ] FastAPI endpoints: `GET /queue`, `POST /approve/{id}`, `POST /regenerate/{id}`
- [ ] Status Kanban: `discovered` → `clipped` → `pending_approval` → `rendering` → `ready` → `published`
- [ ] Preview do clipe (URL assinada MinIO/S3)
- [ ] Exibir roteiro da reação + score de sentimento
- [ ] Botão "Regerar com novo tom" (sarcástico / informativo / humor)
- [ ] (Fase 2) Frontend React com drag-and-drop Kanban

### 4. A/B Testing Títulos e Thumbnails (`ab_testing.py`)
- [ ] LLM gera 3 títulos clickbait saudável por clipe
- [ ] LLM gera 3 hooks de texto para overlay na capa
- [ ] Gerar 3 thumbnails via frame do clímax + texto overlay (Pillow/FFmpeg)
- [ ] Salvar variantes em DB para tracking de performance
- [ ] (Futuro) Métricas de CTR por variante

### 5. Análise de Sentimento (`sentiment.py`)
- [ ] Classificar transcrição: positivo/negativo/neutro/controverso
- [ ] Bloquear auto-publish se sentimento "controverso" sem aprovação
- [ ] Score 0–100 para ordenar fila do dashboard

---

## CHECKLIST — INFRAESTRUTURA & DEVOPS

- [ ] `docker-compose.yml`: PostgreSQL, Redis, MinIO, API, Worker
- [ ] `.env.example` com todas as chaves documentadas
- [ ] `requirements.txt` pinado por versões
- [ ] Pre-commit: black, ruff, mypy (opcional)
- [ ] CI GitHub Actions: lint + pytest
- [ ] Alembic migrations para PostgreSQL
- [ ] Health check `/health` na API
- [ ] Monitoramento de custo APIs (log de tokens/minutos Whisper)

---

## CHECKLIST — SEGURANÇA & COMPLIANCE

- [ ] Nunca commitar `.env` ou API keys
- [ ] Rotacionar chaves trimestralmente
- [ ] Rate limiting nas rotas públicas da API
- [ ] Autenticação JWT no dashboard
- [ ] Aviso legal: uso de conteúdo terceiro — risco de copyright/DMCA
- [ ] Opt-in humano obrigatório antes de publicar (mitigação de ban)
- [ ] Logs de proveniência: URL original, licença inferida, data download

---

## ESTRUTURA DE COMMITS (Conventional Commits)

Padrão: `<tipo>(<escopo>): <descrição curta em imperativo>`

### Tipos permitidos
| Tipo | Uso |
|------|-----|
| `feat` | Nova funcionalidade |
| `fix` | Correção de bug |
| `refactor` | Refatoração sem mudar comportamento |
| `perf` | Melhoria de performance |
| `test` | Testes |
| `docs` | Documentação |
| `chore` | Build, deps, CI |
| `ci` | Pipelines |

### Escopos sugeridos
`miner` | `clipper` | `avatar` | `renderer` | `bypass` | `subtitles` | `api` | `worker` | `ab-test` | `infra`

### Ordem sugerida de commits (MVP)

```
1.  chore(infra): inicializar estrutura do projeto e dependências
2.  feat(miner): esqueleto do módulo de mineração YouTube Shorts
3.  feat(clipper): extração de áudio e integração Whisper
4.  feat(clipper): decisão de corte via LLM com timestamps
5.  feat(clipper): pipeline FFmpeg corte e resize 9:16
6.  feat(bypass): micro-alterações anti-reutilização
7.  feat(subtitles): legendas ASS estilo karaoke
8.  feat(avatar): integração ElevenLabs TTS
9.  feat(avatar): integração HeyGen/D-ID lip-sync
10. feat(renderer): composição clipe + avatar PiP/Duet
11. feat(api): endpoints de fila e aprovação humana
12. feat(sentiment): análise de sentimento pré-aprovação
13. feat(ab-test): gerador de títulos e thumbnails A/B
14. feat(distribution): export HD e webhooks Make/Zapier
15. test(clipper): testes do fluxo transcrição → corte
16. ci(infra): docker-compose e GitHub Actions
17. docs: README de setup e variáveis de ambiente
```

### Exemplo de mensagens
```bash
git commit -m "feat(miner): buscar Shorts por nicho com score de engajamento"
git commit -m "feat(clipper): integrar Whisper API e salvar transcript com timestamps"
git commit -m "fix(renderer): corrigir aspect ratio 9:16 em vídeos 4:3"
git commit -m "feat(api): endpoint POST /approve/{job_id} para fluxo Kanban"
```

### Branches
- `main` — estável, deployável
- `develop` — integração contínua
- `feat/<nome>` — features (ex: `feat/clipper-whisper`)
- `fix/<nome>` — hotfixes

---

## ROADMAP POR FASES

| Fase | Entrega | Prazo sugerido |
|------|---------|----------------|
| **MVP-0** | Estrutura + exemplo `example_clip_flow.py` funcionando local | Semana 1 |
| **MVP-1** | Miner YouTube + Clipper + Bypass + export MP4 | Semana 2–3 |
| **MVP-2** | Avatar + Renderer + Legendas | Semana 4–5 |
| **MVP-3** | API aprovação + A/B titles + Webhook distribuição | Semana 6–7 |
| **Beta** | Dashboard React + TikTok miner + métricas | Semana 8–10 |

---

## VARIÁVEIS DE AMBIENTE (.env)

Ver `.env.example` na raiz do projeto.

---

## COMO RODAR (MVP-1)

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
copy .env.example .env          # preencher chaves

# Terminal 1 — API + Dashboard Kanban
python run_api.py
# Abrir http://127.0.0.1:8000

# Terminal 2 — Minerar Shorts (requer YOUTUBE_API_KEY)
python -m src.pipeline.run_miner --niche curiosidades --download --top 3

# Terminal 2 — Pipeline completo (clip → aprovação → render)
python -m src.pipeline.full_pipeline --input storage/raw/sample.mp4 --niche curiosidades
python -m src.pipeline.full_pipeline --input storage/raw/sample.mp4 --auto-approve

# Só clip (MVP-0)
python -m src.pipeline.example_clip_flow --input storage/raw/sample.mp4

# Teste local SEM APIs (gera sample.mp4 + render completo)
python -m src.pipeline.run_local_test
```

---

*Última atualização: 2026-05-18*
