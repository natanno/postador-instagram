#!/usr/bin/env python3
"""
Atalho para agendar um post sem montar a pasta na mão.

Uso:
  python agendar.py "2026-11-20 18:30" foto.jpg --legenda "Minha legenda #tag"
  python agendar.py "2026-11-21 12:00" reel.mp4 --legenda-arquivo legenda.txt --capa capa.jpg
  python agendar.py "2026-11-22 09:00" 1.jpg 2.jpg 3.jpg --legenda "Carrossel!"
  python agendar.py "2026-11-22 20:00" story.jpg --story

Depois: git add agenda && git commit -m "agenda" && git push
"""
import argparse
import re
import shutil
from datetime import datetime
from pathlib import Path

AGENDA = Path(__file__).resolve().parent / "agenda"

ap = argparse.ArgumentParser()
ap.add_argument("quando", help='data e hora, ex: "2026-11-20 18:30"')
ap.add_argument("arquivos", nargs="+")
ap.add_argument("--legenda", default="")
ap.add_argument("--legenda-arquivo")
ap.add_argument("--capa")
ap.add_argument("--nome", default="post")
ap.add_argument("--story", action="store_true")
a = ap.parse_args()

dt = datetime.strptime(a.quando, "%Y-%m-%d %H:%M")
nome = re.sub(r"[^a-zA-Z0-9-]+", "-", a.nome).strip("-") or "post"
pasta = AGENDA / f"{dt:%Y-%m-%d_%Hh%M}_{nome}{'_story' if a.story else ''}"
pasta.mkdir(parents=True, exist_ok=False)

for i, arq in enumerate(a.arquivos, 1):
    src = Path(arq)
    shutil.copy2(src, pasta / f"{i:02d}{src.suffix.lower()}")
if a.capa:
    shutil.copy2(a.capa, pasta / f"capa{Path(a.capa).suffix.lower()}")

legenda = Path(a.legenda_arquivo).read_text(encoding="utf-8") if a.legenda_arquivo else a.legenda
if legenda:
    (pasta / "legenda.txt").write_text(legenda, encoding="utf-8")

print(f"Agendado em: {pasta.relative_to(AGENDA.parent)}")
