# AI Chief of Staff

Sistema automatizzato di analisi commerciale B2B che legge dati da Google Sheets, genera report manageriali con Claude AI e monitora i KPI del team di vendita.

## Funzionalità

- **Lettura automatica Google Sheets** — sincronizza KPI, CRM e liste prospect (Brasile e Argentina)
- **Report manageriale AI** — genera analisi settimanale con Claude (sezioni: KPI, pipeline CRM, prospect prioritari, alert anomalie)
- **Scheduler automatico** — aggiorna dati e report ogni ora, controlla KPI mancanti ogni giorno alle 09:00
- **Alert CEO** — notifica se i KPI del giorno precedente risultano vuoti o a zero

## Struttura

```
.
├── leggi_sheet.py       # Connessione Google Sheets → dati_canonici.json
├── genera_report.py     # Analisi AI → report_ultimo.txt
├── scheduler.py         # Orchestratore automatico con log
├── .env.example         # Template variabili d'ambiente
└── README.md
```

## Setup

### 1. Dipendenze

```bash
pip install anthropic gspread google-auth schedule
```

### 2. Variabili d'ambiente

```bash
cp .env.example .env
# Modifica .env con i tuoi valori
export ANTHROPIC_API_KEY="sk-ant-api03-..."
```

### 3. Credenziali Google

Posiziona il file JSON del Service Account nella directory del progetto e assicurati che abbia accesso al Google Sheet.

## Utilizzo

### Esecuzione manuale

```bash
# Aggiorna i dati dal foglio
python3 leggi_sheet.py

# Genera il report manageriale
python3 genera_report.py

# Avvia lo scheduler automatico in background
nohup python3 scheduler.py &
```

### Monitoraggio scheduler

```bash
tail -f log.txt        # Log in tempo reale
ps aux | grep scheduler.py   # Verifica processo attivo
```

## Fogli Google supportati

| Tab | Contenuto |
|-----|-----------|
| KPI | Attività giornaliera del team (email, follow-up, chiamate, riunioni) |
| CRM | Pipeline aziendale con stato contatti |
| BRA - Novos a contactar | Prospect Brasile da contattare |
| ARG - Novos a contactar | Prospect Argentina da contattare |

## Note di sicurezza

- Non committare mai il file di credenziali Google (`.json`) né la chiave API
- Usare sempre variabili d'ambiente per i segreti
- Il file `.gitignore` esclude automaticamente tutti i file sensibili
