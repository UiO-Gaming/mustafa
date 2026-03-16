# UiO Gaming Discord Bot

UiO Gaming Discord Bot er en chattebot for ulike formål. Hvilke formål det er, er jeg ikke helt sikker på.

## Kom i gang

0. Lag en botbruker / skaff en token. [Se her](https://discordpy.readthedocs.io/en/stable/discord.html)

1. Lag en kopi av filen [config.yaml.example](src/config/config.yaml.example) i "config" mappen og fjern `.example` fra enden av filnavnet til kopien

2. Fyll inn verdiene i denne konfiguarsjonsfilen

Merk at konfigurasjonsfilen har felt for bl.a. databasekobling. Disse er ikke påkrevd, men du vil derimot miste funksjonalitet om de ikke er fylt inn. Det eneste man *må* fylle inn, som ikke er fylt inn fra før, er `token`.

Gitt en bruker med tilgang til å skrive og lese fra databasen vil botten lage alle tabeller den trenger for å fungere.

Når token er fylt inn kan du så bevege deg videre til ett av to alternativer.

### Valgmulighet 1 - Docker (Anbefalt)

```
docker compose up
```

### Valgmulighet 2 - Manuelt

Du bør ha gjort følgende:

- Installert Python 3.12+

1. Installer avhengigheter

```
pip install -r requirements.txt -U
```

2. Kjør bot

```
python src/run.py
```

## Bidra

Se [CONTRIBUTING.md](CONTRIBUTING.md)
