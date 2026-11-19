#!/usr/bin/env python3
"""
Postador automático do Instagram.

Lê as pastas em agenda/, e publica no Instagram (pela API oficial) toda pasta
cujo horário já chegou. Depois move a pasta para publicados/ (ou falhas/).

Formato de cada pasta em agenda/:
    AAAA-MM-DD_HHhMM_qualquer-nome/
        legenda.txt        -> a legenda (opcional, UTF-8)
        1.jpg              -> 1 imagem = post de foto
        video.mp4          -> 1 vídeo  = Reel
        1.jpg 2.jpg 3.mp4  -> 2 a 10 arquivos = carrossel (ordem alfabética)
        capa.jpg           -> (opcional) capa do Reel
    Coloque "_story" no nome da pasta para publicar como Story.

Só usa a biblioteca padrão do Python (3.9+).
"""
import json
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RAIZ = Path(__file__).resolve().parent
AGENDA = RAIZ / "agenda"
PUBLICADOS = RAIZ / "publicados"
FALHAS = RAIZ / "falhas"

FUSO = ZoneInfo(os.environ.get("FUSO", "America/Sao_Paulo"))
API = os.environ.get("IG_API_BASE", "https://graph.instagram.com").rstrip("/")
VERSAO = os.environ.get("IG_API_VERSION", "v21.0")
TOKEN = os.environ.get("IG_ACCESS_TOKEN", "").strip()
USER_ID = os.environ.get("IG_USER_ID", "").strip()
REPO = os.environ.get("GITHUB_REPOSITORY", "")
BRANCH = os.environ.get("GITHUB_REF_NAME", "main")
MEDIA_BASE = (os.environ.get("MEDIA_BASE_URL") or
              f"https://raw.githubusercontent.com/{REPO}/{BRANCH}").rstrip("/")
DRY_RUN = os.environ.get("DRY_RUN") == "1"
MAX_TENTATIVAS = int(os.environ.get("MAX_TENTATIVAS", "3"))

IMAGENS = {".jpg", ".jpeg"}          # a API do Instagram só aceita JPEG
VIDEOS = {".mp4", ".mov"}
NOME_PASTA = re.compile(r"^(\d{4})-(\d{2})-(\d{2})_(\d{2})h?(\d{2})")


class ErroAPI(Exception):
    pass


# ---------------------------------------------------------------- API
def chamar(metodo, caminho, params=None):
    params = dict(params or {})
    params["access_token"] = TOKEN
    url = f"{API}/{VERSAO}/{caminho}"
    dados = urllib.parse.urlencode(params)
    if metodo == "GET":
        req = urllib.request.Request(f"{url}?{dados}")
    else:
        req = urllib.request.Request(url, data=dados.encode(), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        corpo = e.read().decode(errors="replace")
        raise ErroAPI(f"HTTP {e.code} em {caminho}: {corpo}") from None


def esperar_container(cid, limite=900):
    inicio = time.time()
    while True:
        r = chamar("GET", cid, {"fields": "status_code,status"})
        status = r.get("status_code")
        if status == "FINISHED":
            return
        if status in ("ERROR", "EXPIRED"):
            raise ErroAPI(f"Container {cid} falhou: {r.get('status')}")
        if time.time() - inicio > limite:
            raise ErroAPI(f"Container {cid} demorou demais (status {status})")
        time.sleep(8)


def url_publica(arq: Path) -> str:
    rel = arq.relative_to(RAIZ).as_posix()
    return f"{MEDIA_BASE}/{urllib.parse.quote(rel)}"


def criar_item(arq: Path, **extra):
    params = dict(extra)
    if arq.suffix.lower() in IMAGENS:
        params["image_url"] = url_publica(arq)
    else:
        params["video_url"] = url_publica(arq)
    return chamar("POST", f"{USER_ID}/media", params)["id"]


# ---------------------------------------------------------------- posts
def horario(nome):
    m = NOME_PASTA.match(nome)
    if not m:
        return None
    a, mes, d, h, mi = map(int, m.groups())
    return datetime(a, mes, d, h, mi, tzinfo=FUSO)


def montar(pasta: Path):
    arquivos = sorted(
        p for p in pasta.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGENS | VIDEOS
        and not p.stem.lower().startswith("capa")
    )
    invalidos = [p.name for p in pasta.iterdir()
                 if p.suffix.lower() in {".png", ".webp", ".heic", ".gif"}]
    if invalidos:
        raise ValueError(f"Formato não aceito pela API (use JPG): {invalidos}")
    if not arquivos:
        raise ValueError("Nenhuma imagem (.jpg) ou vídeo (.mp4/.mov) na pasta")
    if len(arquivos) > 10:
        raise ValueError("Carrossel aceita no máximo 10 arquivos")

    leg = pasta / "legenda.txt"
    legenda = leg.read_text(encoding="utf-8").strip() if leg.exists() else ""
    if len(legenda) > 2200:
        raise ValueError(f"Legenda com {len(legenda)} caracteres (máx. 2200)")
    if legenda.count("#") > 30:
        raise ValueError("Mais de 30 hashtags na legenda")

    capa = next((p for p in pasta.iterdir()
                 if p.stem.lower().startswith("capa")
                 and p.suffix.lower() in IMAGENS), None)

    if "_story" in pasta.name.lower():
        if len(arquivos) != 1:
            raise ValueError("Story precisa de exatamente 1 arquivo")
        tipo = "STORY"
    elif len(arquivos) == 1:
        tipo = "REEL" if arquivos[0].suffix.lower() in VIDEOS else "FOTO"
    else:
        tipo = "CARROSSEL"
    return {"tipo": tipo, "arquivos": arquivos, "legenda": legenda, "capa": capa}


def publicar(post):
    tipo, arqs, legenda = post["tipo"], post["arquivos"], post["legenda"]

    if tipo == "FOTO":
        cid = criar_item(arqs[0], caption=legenda)
    elif tipo == "REEL":
        extra = {"media_type": "REELS", "caption": legenda, "share_to_feed": "true"}
        if post["capa"]:
            extra["cover_url"] = url_publica(post["capa"])
        cid = criar_item(arqs[0], **extra)
    elif tipo == "STORY":
        cid = criar_item(arqs[0], media_type="STORIES")
    else:  # CARROSSEL
        filhos = []
        for a in arqs:
            extra = {"is_carousel_item": "true"}
            if a.suffix.lower() in VIDEOS:
                extra["media_type"] = "VIDEO"
            fid = criar_item(a, **extra)
            esperar_container(fid)
            filhos.append(fid)
        cid = chamar("POST", f"{USER_ID}/media", {
            "media_type": "CAROUSEL", "children": ",".join(filhos),
            "caption": legenda})["id"]

    esperar_container(cid)
    return chamar("POST", f"{USER_ID}/media_publish", {"creation_id": cid})["id"]


def mover(pasta: Path, destino: Path):
    destino.mkdir(exist_ok=True)
    alvo = destino / pasta.name
    if alvo.exists():
        alvo = destino / f"{pasta.name}_{int(time.time())}"
    shutil.move(str(pasta), str(alvo))
    return alvo


# ---------------------------------------------------------------- main
def main():
    if not DRY_RUN and (not TOKEN or not USER_ID):
        sys.exit("ERRO: defina IG_ACCESS_TOKEN e IG_USER_ID (secrets do GitHub).")

    agora = datetime.now(FUSO)
    pastas = sorted(p for p in AGENDA.iterdir() if p.is_dir()) if AGENDA.exists() else []
    print(f"[{agora:%d/%m %H:%M}] {len(pastas)} post(s) na agenda")

    for pasta in pastas:
        quando = horario(pasta.name)
        if quando is None:
            print(f"  ! ignorado (nome fora do padrão AAAA-MM-DD_HHhMM): {pasta.name}")
            continue
        if quando > agora:
            print(f"  · aguardando {quando:%d/%m %H:%M}: {pasta.name}")
            continue

        try:
            post = montar(pasta)
            if DRY_RUN:
                print(f"  ✓ [teste] publicaria {post['tipo']} com "
                      f"{len(post['arquivos'])} arquivo(s): {pasta.name}")
                continue
            media_id = publicar(post)
            try:
                link = chamar("GET", media_id, {"fields": "permalink"}).get("permalink")
            except ErroAPI:
                link = None
            (pasta / "publicado.json").write_text(json.dumps({
                "media_id": media_id, "link": link, "tipo": post["tipo"],
                "agendado": quando.isoformat(),
                "publicado": datetime.now(FUSO).isoformat(),
            }, ensure_ascii=False, indent=2), encoding="utf-8")
            mover(pasta, PUBLICADOS)
            print(f"  ✓ publicado {post['tipo']}: {pasta.name} -> {link}")
        except Exception as e:  # noqa: BLE001
            cont = pasta / "tentativas.txt"
            n = int(cont.read_text()) + 1 if cont.exists() else 1
            cont.write_text(str(n))
            (pasta / "erro.txt").write_text(f"{datetime.now(FUSO).isoformat()}\n{e}\n",
                                            encoding="utf-8")
            if isinstance(e, ValueError) or n >= MAX_TENTATIVAS:
                mover(pasta, FALHAS)
                print(f"  ✗ FALHOU (movido para falhas/): {pasta.name}: {e}")
            else:
                print(f"  ✗ erro (tentativa {n}/{MAX_TENTATIVAS}, tenta de novo): {e}")


if __name__ == "__main__":
    main()
