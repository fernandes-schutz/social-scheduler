# -*- coding: utf-8 -*-
# Publica posts agendados no Instagram e no Facebook.
# Le schedule.csv, encontra as linhas cujo horario ja chegou,
# publica, e registra o resultado em published.csv.
# Usa apenas a biblioteca padrao (urllib) - sem dependencias externas.

import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# ---------------------------------------------------------------------------
# Configuracao
# ---------------------------------------------------------------------------

API = "https://graph.facebook.com/v21.0"

TOKEN = os.environ.get("META_TOKEN", "")
PAGE_ID = os.environ.get("FB_PAGE_ID", "")
IG_ID = os.environ.get("IG_USER_ID", "")
REPO = os.environ.get("GITHUB_REPOSITORY", "")
BRANCH = os.environ.get("GITHUB_REF_NAME", "main")

# Fuso dos horarios escritos no schedule.csv
TZ = ZoneInfo("America/New_York")

# Modo de teste: nao publica nada, so mostra o que faria.
# Vale "1" para ligar. Padrao é ligado por seguranca.
DRY_RUN = os.environ.get("DRY_RUN", "1") == "1"

# Nao publica post cujo horario ja passou ha mais que isso.
# Evita que uma pausa longa dispare uma enxurrada de posts atrasados.
JANELA_HORAS = 12

# Limite de posts por execucao. Util para testar em lote pequeno.
LIMIT = int(os.environ.get("LIMIT", "10"))

SCHEDULE = "schedule.csv"
PUBLISHED = "published.csv"


# ---------------------------------------------------------------------------
# Utilidades HTTP
# ---------------------------------------------------------------------------

def post(caminho, campos, token=None):
    """Faz um POST no Graph API e devolve a resposta como dicionario."""
    campos = dict(campos)
    campos["access_token"] = token or TOKEN
    dados = urllib.parse.urlencode(campos).encode("utf-8")
    req = urllib.request.Request(API + caminho, data=dados, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def get(caminho, campos=None, token=None):
    """Faz um GET no Graph API e devolve a resposta como dicionario."""
    campos = dict(campos or {})
    campos["access_token"] = token or TOKEN
    url = API + caminho + "?" + urllib.parse.urlencode(campos)
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


# O Facebook exige um token da propria Pagina para publicar nela.
# O Instagram aceita o token do usuario do sistema direto; o Facebook nao.
_token_pagina = None


def token_da_pagina():
    global _token_pagina
    if _token_pagina is None:
        r = get("/%s" % PAGE_ID, {"fields": "access_token"})
        _token_pagina = r["access_token"]
    return _token_pagina


# ---------------------------------------------------------------------------
# Publicacao
# ---------------------------------------------------------------------------

def url_da_imagem(nome):
    """Monta o endereco publico da imagem dentro do proprio repositorio."""
    return "https://raw.githubusercontent.com/%s/%s/posts/%s" % (
        REPO, BRANCH, urllib.parse.quote(nome))


def publica_instagram(img_url, legenda):
    """Instagram publica em dois tempos: cria o container, depois publica."""
    c = post("/%s/media" % IG_ID, {"image_url": img_url, "caption": legenda})
    cid = c["id"]

    # O container leva alguns segundos para ficar pronto.
    for _ in range(20):
        st = get("/%s" % cid, {"fields": "status_code,status"})
        if st.get("status_code") == "FINISHED":
            break
        if st.get("status_code") == "ERROR":
            raise RuntimeError("container com erro: %s" % st.get("status"))
        time.sleep(5)
    else:
        raise RuntimeError("container nao ficou pronto a tempo")

    r = post("/%s/media_publish" % IG_ID, {"creation_id": cid})
    return r["id"]


def publica_facebook(img_url, legenda):
    """Facebook aceita foto e texto numa chamada so."""
    r = post("/%s/photos" % PAGE_ID, {
        "url": img_url,
        "caption": legenda,
        "published": "true",
    }, token=token_da_pagina())
    return r.get("post_id") or r.get("id")


# ---------------------------------------------------------------------------
# Estado
# ---------------------------------------------------------------------------

def ja_publicados():
    """Chaves dos posts que ja foram publicados, para nao repetir."""
    if not os.path.exists(PUBLISHED):
        return set()
    with open(PUBLISHED, newline="", encoding="utf-8") as f:
        return {l["chave"] for l in csv.DictReader(f)}


def registra(chave, rede, ident):
    novo = not os.path.exists(PUBLISHED)
    with open(PUBLISHED, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if novo:
            w.writerow(["chave", "rede", "id", "quando"])
        w.writerow([chave, rede, ident, datetime.now(TZ).isoformat()])


# ---------------------------------------------------------------------------
# Principal
# ---------------------------------------------------------------------------

def main():
    if not TOKEN or not PAGE_ID or not IG_ID:
        print("ERRO: faltam META_TOKEN, FB_PAGE_ID ou IG_USER_ID.")
        return 1

    agora = datetime.now(TZ)
    feitos = ja_publicados()
    contador = 0
    falhas = 0

    with open(SCHEDULE, newline="", encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))

    for linha in linhas:
        if contador >= LIMIT:
            break

        quando = datetime.strptime(
            "%s %s" % (linha["data"].strip(), linha["hora"].strip()),
            "%Y-%m-%d %H:%M").replace(tzinfo=TZ)

        if quando > agora:
            continue
        if agora - quando > timedelta(hours=JANELA_HORAS):
            continue

        redes = [r.strip() for r in linha["redes"].lower().split("+")]
        img = url_da_imagem(linha["imagem"].strip())
        legenda = linha["legenda"]

        for rede in redes:
            chave = "%s|%s|%s" % (linha["data"], linha["hora"], rede)
            if chave in feitos:
                continue

            if DRY_RUN:
                print("[teste] publicaria em %s: %s" % (rede, linha["imagem"]))
                continue

            try:
                if rede == "ig":
                    ident = publica_instagram(img, legenda)
                elif rede == "fb":
                    ident = publica_facebook(img, legenda)
                else:
                    print("rede desconhecida: %s" % rede)
                    continue
                registra(chave, rede, ident)
                print("publicado em %s: %s (%s)" % (rede, linha["imagem"], ident))
                contador += 1
            except urllib.error.HTTPError as e:
                # A mensagem util da Meta vem no corpo da resposta, nao no codigo.
                detalhe = e.read().decode("utf-8", "replace")
                print("FALHOU em %s (%s): %s | %s" % (
                    rede, linha["imagem"], e, detalhe))
                falhas += 1
            except Exception as e:
                print("FALHOU em %s (%s): %s" % (rede, linha["imagem"], e))
                falhas += 1

    if DRY_RUN:
        print("\nModo de teste. Nada foi publicado de verdade.")

    # Terminar com erro faz a execucao ficar vermelha no GitHub, que e o que
    # dispara o e-mail e a notificacao. Sem isso, post que nao saiu passa
    # despercebido porque a execucao aparece verde.
    if falhas:
        print("\n%d publicacao(oes) falharam." % falhas)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
