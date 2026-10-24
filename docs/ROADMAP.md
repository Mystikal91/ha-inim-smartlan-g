# Roadmap

## Prima di pubblicare
- [x] Sostituire `OWNER` (repository `Mystikal91/ha-inim-smartlan-g`)
- [x] LICENSE (MIT)
- [x] CI GitHub scritta (`.github/workflows/validate.yml`: hassfest, HACS, ruff, test); da vedere verde al primo push
- [ ] Test del livello HA con `pytest-homeassistant-custom-component` (config flow, coordinator, entità, reauth)
- [ ] Ruotare password/codice della centrale (i token sono comparsi in file di cattura)

## Funzioni
- [x] Diagnosi `cmd` vuoto: causa = codice installatore, con codice utente le uscite compaiono
- [ ] Verificare `do_cmd` su un'uscita reale e documentare il codice utente nel README
- [x] Reset memoria allarme (`do_part` act=5): pulsante per partizione, sempre disponibile come nella webapp; da verificare su impianto reale
- [x] Esclusione zone (`do_zone`): switch di configurazione per zona, disabilitato di default; `act` 1=escludi, 0=includi preso dai pulsanti della webapp, **da verificare su una zona non critica a impianto disinserito**
- [x] Log eventi: sensore "Last event" (ultimo evento, lento). Da fare: eventi in tempo reale/bus eventi, verificare fuso orario di `dt`
- [x] Timer (`tmr`) in sola lettura (binary_sensor diagnostici, disabilitati di default); significato di `st` da verificare
- [x] Pre-controllo zone non pronte (`nrzs`/`nrza`): blocca l'arma con elenco zone (firmware >= 5); da verificare su impianto reale
- [x] Intervalli di polling separati: stato (partizioni/scenario/uscite), zone, dati lenti (guasti/GSM/timer/log); `PollSchedule` in `schedule.py`
- [x] Diagnostics (`diagnostics.py`): struttura e codici di stato grezzi, senza credenziali, IP, token né nomi (zone, partizioni, utenti, luoghi); da verificare in HA
- [ ] Verifica maschera zone > 31 e comportamento con molte zone

- [x] Notifiche opzionali (cambio scenario, uscita attiva) + eventi `inim_smartlan_scenario_changed` / `inim_smartlan_output_active`; da verificare in HA

## Idee
- Analisi dell'app Inim Home (cattura con PCAPdroid) se mancano funzioni o eventi in tempo reale
