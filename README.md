# UiO Gaming Discord Bot

UiO Gaming Discord Bot er en chattebot for ulike formål. Hvilke formål det er, er jeg ikke helt sikker på.

## Kom i gang

0. Lag en botbruker / skaff en token. [Se her](https://discordpy.readthedocs.io/en/stable/discord.html). Skru også på alle tre _Privileged Gateway Intents_ (Presence, Server Members og Message Content) under "Bot" i Developer Portal. Botten ber om alle intents og starter ikke uten dem

1. Lag en kopi av filen [config.yaml.example](src/config/config.yaml.example) i "config" mappen og fjern `.example` fra enden av filnavnet til kopien

2. Fyll inn verdiene i denne konfiguarsjonsfilen

Merk at konfigurasjonsfilen har felt for bl.a. databasekobling. Disse er ikke påkrevd, men du vil derimot miste funksjonalitet om de ikke er fylt inn. Det eneste man _må_ fylle inn, som ikke er fylt inn fra før, er `token`.

`config_mode` bestemmer hvor slash-kommandoene synkroniseres. Med `dev` synkroniseres de bare til serveren i `dev_guild`, der de dukker opp med en gang. Med `prod` synkroniseres de globalt.

Bruk en egen botbruker når du utvikler lokalt. Kjører du `dev` med samme token som produksjonsbotten, får serveren i `dev_guild` både de globale kommandoene og kopiene, og alle kommandoer vises to ganger. Botten logger en advarsel når det skjer. I `prod` fjernes kommandoer som er igjen i `dev_guild` fra tidligere `dev`-kjøringer automatisk.

### Valgfrie funksjoner

Mangler et felt, skrus funksjonene som trenger det av når botten starter:

| Felt | Funksjoner |
| --- | --- |
| `database` | Bursdager, autosvar, gullkorn, Minecraft-whitelist, social credit, stjernetavla, streaks, høyde og MBTI, ordsky |
| `minecraft` | Minecraft-whitelist. Botten kobler til RCON på `127.0.0.1:25575`, så Minecraft-serveren må kjøre på samme maskin |
| `sanity` | Synkronisering av arrangementer til nettsiden |
| `galtinn` | `/galtinn medlemskap` |
| `ids` | Funksjoner som trenger en kanal, rolle eller bruker. De som mangler en ID hoppes over |

Databasen må være PostgreSQL. Gitt en bruker med tilgang til å skrive og lese fra databasen vil botten lage alle tabeller den trenger for å fungere.

Når token er fylt inn kan du så bevege deg videre til ett av to alternativer.

### Valgmulighet 1 - Docker (Anbefalt)

```
docker compose up --build
```

Konfigurasjonsfilen kopieres inn i imaget når det bygges, så husk `--build` etter at du har endret den. Containeren bruker vertens nettverk, slik at den når databasen og Minecraft-serveren på `localhost`.

### Valgmulighet 2 - Manuelt

Du bør ha gjort følgende:

- Installert [uv](https://docs.astral.sh/uv/)
- Installert `ffmpeg`, `graphviz` og `pandoc`

1. Installer avhengigheter

```
uv sync
```

2. Kjør bot fra rotmappen til prosjektet

```
uv run src/run.py
```

## Bidra

Se [CONTRIBUTING.md](CONTRIBUTING.md)
