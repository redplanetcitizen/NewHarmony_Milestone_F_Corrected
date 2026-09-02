# NewHarmony F Corrected Eco — pacchetto autonomo

Questa distribuzione può essere inviata direttamente a uno sviluppatore terzo.
Non richiede un clone GitHub separato: contiene il motore necessario, i dati,
i risultati di riferimento, la contabilità ecologica ex post, il cruscotto e
gli strumenti di verifica.

## Avvio rapido su Windows

Fare doppio clic su `PREPARA_E_AVVIA.bat`.

Lo script crea un ambiente Python locale nella cartella del pacchetto, installa
NumPy e SciPy e quindi:

1. verifica la copia incorporata di Milestone F Corrected;
2. riesegue in memoria le modalità prospettica e storico-diagnostica;
3. confronta i risultati con i valori pubblicati;
4. genera la contabilità ecologica;
5. apre il cruscotto su `http://127.0.0.1:8765/`.

Se le dipendenze sono già installate è possibile usare `ESEGUI_ECO.bat`.
Per riaprire soltanto un cruscotto già generato usare `APRI_CRUSCOTTO.bat`.

## Avvio da terminale

```bash
python -m pip install -r requirements.txt
python run_standalone.py
python run_standalone.py --serve
```

## Struttura

- `engine/`: snapshot operativo byte-per-byte di Milestone F Corrected;
- `companion/`: adattatore, contabilità ecologica, cruscotto e test;
- `outputs/`: risultati già generati e rapporto di validazione;
- `ENGINE_PROVENANCE.json`: repository e commit di provenienza;
- `ENGINE_INTEGRITY.json`: hash di ogni file incorporato del motore;
- `DISTRIBUTION_MANIFEST.json`: hash dell'intera distribuzione;
- `verify_distribution.py`: controllo offline dell'integrità.

## Separazione dal motore

Il companion non importa dati modificati e non scrive in `engine/`. Prima e
dopo ogni esecuzione calcola una firma completa; qualsiasi cambiamento provoca
l'interruzione del processo. Gli output vengono scritti esclusivamente in
`outputs/` e il dataset del cruscotto in `companion/dashboard/data.json`.

## Portata ecologica

Il cruscotto separa due letture. La matrice 0/1/2 è mostrata soltanto come mappa
di associazioni `nessuna`, `operativa` e `caratteristica`: non produce quantità
né semafori. La matrice fisica stima invece masse dirette in kg, usando
coefficienti 2012 e un rapporto di attività reale riferito al 2019 per evitare
la moltiplicazione fra valori monetari espressi in anni-prezzo diversi.

Il selettore `Settore` comprende tutti i 71 settori del motore. La scelta
`Tutti i settori` mantiene la vista aggregata; la scelta di un singolo settore
mostra anno per anno l'output realizzato rispetto al fabbisogno-obiettivo, la
Harmony diagnostica settoriale, la massa dell'inquinante selezionato e il
profilo degli inquinanti principali. Per i
cinque settori non raccordati il percorso economico resta visibile, mentre il
dato ecologico è correttamente indicato come `n.d.`.

Il colore verde/giallo/arancione/rosso descrive soltanto la variazione della
massa aggregata rispetto al 2019 e non la pericolosità tossicologica. Sul
singolo settore resta `n.d.` finché non sono disponibili soglie specifiche
documentate o intensità variabili nel tempo.

## Materiale archivistico non incluso

Le due copie compresse dei predecessori Milestone E presenti nella sezione
`reference/` del repository GitHub non sono necessarie per eseguire o verificare
Milestone F e avrebbero aggiunto circa 39,5 MB. Sono quindi identificate, ma non
duplicate, in `ENGINE_PROVENANCE.json`. Tutti i file necessari all'esecuzione
sono inclusi.
