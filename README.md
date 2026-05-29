# Daglig aktie-watchlist (Codex/GitHub Actions)

Dette projekt er en robust erstatning for ChatGPT Tasks, så du kan få en daglig dansk aktie-watchlist sendt på e-mail før USA-markedet åbner.

## Hvad løsningen gør

- Kører hverdage via GitHub Actions.
- Henter daglige OHLCV-data for en watchlist af amerikanske aktier.
- Frasorterer ETF'er ved kun at bruge tickers fra `tickers.txt`.
- Beregner Williams %R, glidende gennemsnit, volumen-ratio og simple momentum-signaler.
- Rangerer aktier og sender topkandidater via Gmail SMTP.

## Hurtig opsætning

1. Opret et nyt GitHub repository.
2. Upload alle filerne i denne mappe.
3. Ret `tickers.txt` efter dine ønsker.
4. Gå til GitHub repo -> Settings -> Secrets and variables -> Actions -> New repository secret.
5. Opret disse secrets:

| Secret | Beskrivelse |
|---|---|
| `SMTP_HOST` | Typisk `smtp.gmail.com` |
| `SMTP_PORT` | Typisk `587` |
| `SMTP_USER` | Din Gmail-adresse |
| `SMTP_PASSWORD` | Gmail App Password, ikke din normale Gmail-adgangskode |
| `EMAIL_TO` | Modtager, fx `kimnissen1@gmail.com` |
| `EMAIL_FROM` | Afsender, typisk samme som `SMTP_USER` |

## Gmail App Password

For Gmail skal du normalt aktivere 2-trinsbekræftelse og oprette et App Password. Brug dette som `SMTP_PASSWORD`.

## Tidspunkt

GitHub Actions bruger UTC. Workflowet kører kl. 12:15 UTC og 13:15 UTC på hverdage. Scriptet tjekker selv, om lokal tid i København er omkring 14:15, så det håndterer sommer-/vintertid.

## Lokal test

```bash
pip install -r requirements.txt
python src/watchlist.py --dry-run
```

For at sende mail lokalt skal miljøvariablerne være sat.

## Vigtigt

Dette er ikke finansiel rådgivning. Scriptet laver en systematisk watchlist baseret på historiske dagsdata og tekniske signaler. Brug altid egen handelsplatform til at verificere realtidspris, volumen, spreads, nyheder, entry og stop-loss.
