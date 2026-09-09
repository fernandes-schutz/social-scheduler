# social-scheduler

Publica automaticamente no Instagram e no Facebook da The Hound & Roast Society,
sem depender de computador ligado. Roda na nuvem do GitHub.

## Como usar toda semana

1. Suba as artes na pasta `posts/`
2. Edite `schedule.csv` com data, hora, arquivo e legenda
3. Pronto. O resto acontece sozinho.

## Formato do schedule.csv

```
data,hora,imagem,legenda,redes
2026-09-17,07:00,post01.png,"Texto da legenda",ig+fb
```

- **data** — `AAAA-MM-DD`
- **hora** — `HH:MM`, horário de Nova York
- **imagem** — nome do arquivo dentro de `posts/`
- **legenda** — entre aspas se tiver vírgula
- **redes** — `ig`, `fb`, ou `ig+fb`

## Como funciona

A cada 15 minutos o GitHub roda o `publish.py`. Ele olha o `schedule.csv`,
pega as linhas cujo horário já chegou e ainda não foram publicadas, e publica.
Depois anota em `published.csv` para não repetir.

O Instagram exige que a imagem esteja num endereço público. É por isso que o
repositório é público: as artes ficam acessíveis por link, e a Meta consegue
buscá-las. Nada sigiloso mora aqui.

## Segurança

As senhas de acesso **não ficam em arquivo**. Elas vivem nos Secrets do
repositório (Settings → Secrets and variables → Actions):

- `META_TOKEN` — token permanente do usuário do sistema
- `FB_PAGE_ID` — identificação da Página do Facebook
- `IG_USER_ID` — identificação da conta do Instagram

## Testar sem publicar

Actions → "Publicar posts" → **Run workflow** → deixe `dry_run` em `1`.
Ele mostra o que faria, sem postar nada.

## Limites conhecidos

- O agendamento do GitHub pode atrasar alguns minutos. Para post de rede
  social isso não costuma importar.
- Posts com mais de 12 horas de atraso são ignorados, para não disparar uma
  enxurrada caso a automação fique parada.
- Instagram aceita no máximo 100 publicações por API a cada 24 horas.
