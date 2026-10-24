# Sviluppo

## Ambiente
```
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements_dev.txt
python tests/test_api.py
```

## Provare su Home Assistant
Copia `custom_components/inim_smartlan` in `<config>/custom_components/`, riavvia Home Assistant
(riavvio completo), poi *Impostazioni → Dispositivi e servizi → Aggiungi integrazione → INIM SmartLAN*.
Log: *Impostazioni → Sistema → Registri*, filtro "inim"; per il debug aggiungi in `configuration.yaml`:
```
logger:
  logs:
    custom_components.inim_smartlan: debug
```

## Diagnostica sulla centrale
`python tools/probe.py --host IP --port PORTA --user UTENTE` (sola lettura, non salva token né credenziali;
controlla comunque il JSON per nomi di persone/stanze prima di condividerlo).

## Segreti
Non committare mai `*.har`, `*.pcap`, `probe_output*.json`. Vedi `.gitignore`.
