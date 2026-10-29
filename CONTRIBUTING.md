# Bidragsguide

Heisann sveisann! Er du interessert i å bidra? Kult!

Det er derimot noen kodestilsregler jeg ønsker at skal følges. Dette dokumentet fungerer som en defacto regelbok for både meg og/eller andre.

## Oppsett

Se [README.md](README.md) for hvordan du kjører botten. Installer i tillegg pre-commit-hookene:

```
uv sync
uv run pre-commit install
```

De kjører black, isort og ruff (linjelengde 120) før hver commit. De samme sjekkene kjøres i GitHub Actions på alle pushes og pull requests.

## Regler

### Typing

All kode skal være typet til beste evne. Dette betyr at man for eksempel også gjerne bør spesifisere typene innad i en dict eller lignende.

### Docstrings

Alle funksjoner skal ha docstrings som følger denne stilen:

```python
def greet(self, name: str) -> str:
    """
    Greets the invoking user using the inputted name

    Parameters
    ----------
    name (str): The user's inputted name

    Returns
    ----------
    (str): A greeting
    """

    return f"Hello, {name}"
```

Sløyf alt som ikke brukes.

Skriv unioner som `a | b`, og returverdien som `(type): beskrivelse`. Valgfrie parametere skal si hva standardverdien er, f.eks. `Defaults to the invoking user`. Noen parametere går igjen overalt, og beskrives likt:

- `interaction (discord.Interaction): The slash command interaction` i slash-kommandoer, og `The interaction that triggered this` i knapper, menyer og alt annet
- `ctx (commands.Context): The command context`
- `bot (commands.Bot): The bot instance`

### Importering

isort sorterer importene med én import per linje. Egne moduler importeres som moduler, som `from cogs.utils import misc_utils`, og brukes som `misc_utils.Paginator`.

### Rekkefølge på kommandosjekker (decorators)

Hver kommando er en funksjon som har et eller flere decorators over seg. Dette er sjekker som utføres før kommandoen kjøres. En av disse konverterer også funksjonen til en faktisk kommando som vi kan kjøre gjennom Discord.

Decorators skal sorteres som følgende:

1. is owner
2. Guild only
3. Bot permissions
4. User permissions
5. Cooldown
6. Kommando (denne må alltid være med)
7. Parameternavn (`rename`)
8. Parameterbeskrivelser (`describe`)

Merk deg at ikke alle disse trenger å være med, og ikke alle sjekker som finnes er nevnt her. Bruk hodet og tenk hva som er logisk for deg om du møter på en slik situasjon.

### Newline mellom docstring og kode samt mellom siste kodelinje returstatement

Ja, det tittelen sier. Det er et unntak for returstatements hvis det er tatt i bruk early returning.

### Norske parameternavn og beskrivelser i kommandoer

Selv om Discord.py 2.0 støtter oversettelser, er ikke dette noe vi implementerer. Botten er norsk og for norske brukere, så alt Discord viser av parametere skal være på norsk. I koden har parameterne likevel engelske navn. Gi dem et norsk navn i Discord med `@app_commands.rename` og en norsk beskrivelse med `@app_commands.describe`. Alle parametere skal ha en beskrivelse. Plasser disse rett under decoratoren for kommandoen:

```python
@app_commands.command(name="hils", description="Hils på en bruker")
@app_commands.rename(user="bruker")
@app_commands.describe(user="Brukeren du vil hilse på")
async def greet(self, interaction: discord.Interaction, user: discord.User):
```

`rename` kan sløyfes om navnet er likt på begge språk, som f.eks `url`.

### Engelsk for alt annet

All annen kode holdes på engelsk. Dette inkluderer kommentarer.

Et tips er å ha et engelsk funksjonsnavn, men spesifisere i decoratoren over med navnparameteren.

### Bruk av embed templates

`error_warning` skal brukes om det er feil brukerinput, mangel på data eller generelt sett en feil som er forventet/ikke av utenforstående årsaker

`error_fatal` brukes når en uventet feil skjer. Ofte på grunn av utenforstående årsaker som et API som er nede osv.

`success` kan brukes til å gi brukeren en bekreftelse på at operasjonen som ble forespurt gikk fint. Det vil si at den ikke skal brukes til å vise spesifikk data, men heller brukes når det ikke er noe å vise.

### Bruk av private variabler/metoder

Generelt sett unngår vi bruk av leading underscores for variabelnavn og metoder. Ja, de har sin bruk, men Python var aldri ment til å være objektorientert på samme måte som f.eks Java. Uansett skal en ikke bruke metoder fra andre cogs. Dermed er regelen: greit overalt utenom i cogs.

### Tid og tidssoner

Bruk alltid tidssonebevisste datetime-objekter. Bruk `discord.utils.utcnow()` for nåtid og `self.bot.timezone` for å regne om til lokal tid. `misc_utils.localize` gir en naiv datetime en tidssone uten å endre klokkeslettet.

### Bakgrunnsoppgaver

Legg `@misc_utils.log_errors` rett under `@tasks.loop`, slik at en feil blir logget i stedet for å stoppe løkka. Daglige løkker kjøres med `time=misc_utils.MIDNIGHT`, som er midnatt i bottens tidssone.

### Nye cogs

Legg filen i `src/cogs` med en `setup`-funksjon nederst. Alle cogs der lastes automatisk. Trenger cogen databasen, legg filnavnet til i `DATABASE_RELIANT_COGS` i `src/run.py` og lag tabellene den trenger i `cog_load`. Kanal-, rolle- og bruker-IDer legges under `ids` i konfigurasjonsfilen og hentes med `self.bot.channel_ids`, `self.bot.role_ids` og `self.bot.user_ids`.

### Avhengigheter

Hvis en ny avhengighet trengs, legg den til med `uv add "pakke==X.Y.*"` slik at major og minor versjon er spesifisert. Trengs et systemprogram, legg det til i `apt-get install`-linja i `Dockerfile` og i README-en.

## Ønsket utforming av ny funksjonalitet

- Bruk embeds til feilmeldinger og som respons om mulig.
- Sett cooldown til 5 sekunder for kommandoer som krever eksterne API kall eller særlig mye prosessering.
  - Ellers, settes denne til 2 sekunder.
