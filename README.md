# Postador automático do Instagram

Agenda posts (foto, Reel, carrossel e Story) com legenda e publica sozinho no
horário marcado, direto pela **API oficial do Instagram**. Sem Metricool, sem
site de agendamento: roda grátis no GitHub Actions e não precisa do seu PC ligado.

## Como funciona

```
agenda/                          <- você coloca os posts aqui
  2026-11-20_18h30_dica-do-dia/
    legenda.txt
    01.jpg
publicados/                      <- o robô move pra cá depois de postar (com o link)
falhas/                          <- se der erro, vem pra cá com erro.txt explicando
```

A cada 10 minutos o GitHub roda `postador.py`. Toda pasta cujo horário já passou
é publicada e movida para `publicados/`.

| Conteúdo da pasta            | Vira          |
|------------------------------|---------------|
| 1 `.jpg`                     | Foto no feed  |
| 1 `.mp4`/`.mov`              | Reel (+ `capa.jpg` opcional) |
| 2 a 10 arquivos              | Carrossel (ordem alfabética) |
| nome da pasta com `_story`   | Story         |

Horário no nome da pasta, no fuso de Brasília: `AAAA-MM-DD_HHhMM_nome`.

---

## Configuração (uma vez só, ~20 min)

### 1. Conta do Instagram
A conta precisa ser **Profissional** (Criador de conteúdo ou Empresa).
Instagram → Configurações → Tipo de conta e ferramentas → Mudar para conta profissional.

### 2. Criar o app na Meta e gerar o token
1. Acesse **developers.facebook.com** → *Meus apps* → *Criar app*.
2. Caso de uso: **"Gerenciar mensagens e conteúdo no Instagram"** (API do Instagram com login do Instagram — não precisa de Página do Facebook).
3. No painel do app: *API do Instagram* → *Configuração da API com login do Instagram*.
4. Em **"Gerar tokens de acesso"**, clique em *Adicionar conta*, entre com o seu Instagram e autorize as permissões `instagram_business_basic` e `instagram_business_content_publish`.
5. Clique em **Gerar token** e copie (é o `IG_ACCESS_TOKEN`, vale 60 dias).
6. Descubra seu ID abrindo no navegador:
   `https://graph.instagram.com/v21.0/me?fields=user_id,username&access_token=SEU_TOKEN`
   O número em `user_id` é o `IG_USER_ID`.

> Enquanto o app estiver em modo "Desenvolvimento", ele funciona para a sua própria conta — é o suficiente aqui. Não precisa enviar para revisão da Meta.

### 3. Subir no GitHub
1. Crie um repositório **público** (ex.: `postador-instagram`) e envie estes arquivos.
   *Público porque a Meta precisa baixar as imagens/vídeos por um link aberto.*
2. *Settings → Secrets and variables → Actions → New repository secret*:
   - `IG_ACCESS_TOKEN` = o token
   - `IG_USER_ID` = o número do user_id
   - `GH_PAT` (opcional, recomendado) = um token do GitHub (*Settings → Developer settings → Fine-grained tokens*, acesso só a este repo, permissão **Secrets: Read and write**). Com ele o token do Instagram é renovado sozinho a cada 15 dias.
3. *Actions* → habilite os workflows → abra "Postador Instagram" → **Run workflow** para testar.

---

## Agendar um post

**Pelo atalho (no seu PC, com o repo clonado):**
```bash
python agendar.py "2026-11-20 18:30" foto.jpg --legenda "Legenda aqui #hashtag" --nome dica
python agendar.py "2026-11-21 12:00" reel.mp4 --legenda-arquivo legenda.txt --capa capa.jpg
python agendar.py "2026-11-22 09:00" 1.jpg 2.jpg 3.jpg --legenda "Carrossel"
git add agenda && git commit -m "agenda" && git push
```

**Ou pelo Claude:** me mande os arquivos, a legenda e o horário e eu crio a pasta e faço o push no seu repositório.

**Teste sem publicar:** `DRY_RUN=1 python postador.py` mostra o que seria postado.

---

## Limites que valem saber
- **Imagens só em JPG.** PNG/WebP/HEIC são recusados pela API (o post vai para `falhas/` com o motivo).
- **Atraso de alguns minutos:** o agendador do GitHub roda a cada 10 min e às vezes atrasa um pouco em horários de pico. Um post das 18:30 sai entre 18:30 e ~18:45.
- **Repositório público:** quem souber o endereço vê os posts agendados antes da hora. Se isso incomodar, dá para servir as mídias por outro link (variável `MEDIA_BASE_URL`).
- **Legenda:** máx. 2.200 caracteres e 30 hashtags. Story via API não leva legenda.
- **Limite diário da Meta** para publicações via API (bem acima de um uso normal).
- Erros temporários são tentados de novo até 3 vezes; erros de conteúdo vão direto para `falhas/`.
- Se o Reel falhar com erro de mídia, confira: H.264/AAC, 9:16, até 15 min, até ~300 MB.
