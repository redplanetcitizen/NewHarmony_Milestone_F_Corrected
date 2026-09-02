# NewHarmony F Corrected — Eco Companion

Questo pacchetto aggiunge a **Milestone F Corrected** una contabilità ecologica
ex post e un cruscotto locale senza modificare il motore originale.

## Principio di separazione

Milestone F Corrected è trattato come sorgente di sola lettura. Il companion:

1. calcola una firma SHA-256 completa della sorgente;
2. carica il solver originale e ricostruisce in memoria i risultati finali;
3. esporta l'output lordo per settore e anno in una cartella esterna;
4. applica separatamente la matrice qualitativa 0/1/2 e la matrice dei coefficienti fisici;
5. genera dati e pagine del cruscotto;
6. ricalcola la firma e interrompe l'esecuzione se un solo file sorgente è cambiato.

Non vengono aggiunti file, cache Python o risultati nella cartella di Milestone F.

## Avvio

Installare le dipendenze:

```bash
python -m pip install -r requirements.txt
```

Generare i risultati, indicando la cartella del clone originale:

```bash
python run_companion.py --milestone-root PATH/TO/NewHarmony_Milestone_F_Corrected
```

Per avviare anche il cruscotto locale:

```bash
python run_companion.py --milestone-root PATH/TO/NewHarmony_Milestone_F_Corrected --serve
```

Su Windows è possibile trascinare la cartella di Milestone F Corrected sopra
`ESEGUI_E_APRI_CRUSCOTTO.bat`, oppure passare il percorso come primo argomento.

## Interpretazione ecologica

Il cruscotto mantiene due livelli distinti. `Associazioni qualitative` presenta
0/1/2 esclusivamente come categorie: nessuna associazione, associazione
operativa, associazione caratteristica. Non costruisce quantità, traiettorie o
semafori da questa matrice.

`Masse fisiche` usa coefficienti diretti in kg per milione di dollari 2012. Per
evitare di confondere anni-prezzo diversi, il coefficiente viene applicato
all'output di base 2012 e la massa risultante viene riscalata con il rapporto
adimensionale fra output reale pianificato e output reale osservato 2019. Il
metodo completo è documentato in `data/METODO_CONTABILITA_FISICA.md`.

Il raccordo 71→72 è documentato in `data/crosswalk_f71_to_eco72.csv`. Le
disaggregazioni non identificabili dai dati di F usano quote paritarie e sono
marcate come proxy. I cinque settori pubblici privi di corrispondenza nella
matrice ecologica restano esplicitamente non mappati e sono esclusi dai totali
ecologici; il cruscotto mostra sempre la quota di output coperta.

Il cruscotto permette di selezionare tutti i 71 settori del motore. Per il
settore selezionato mostra anno per anno la percentuale di output lordo
realizzato rispetto al fabbisogno-obiettivo e la corrispondente Harmony
diagnostica settoriale. Il fabbisogno comprende produzione sociale e beni di
investimento. Questa Harmony è una lettura ex post, non una nuova variabile del
solver e non modifica la Harmony globale di Milestone F Corrected.

Il segnale verde/giallo/arancione/rosso è disponibile soltanto per la massa
fisica aggregata ed esprime la variazione rispetto al 2019. Non è una
classificazione tossicologica. Sul singolo settore è indicato `n.d.` perché,
con intensità costanti, servono soglie settoriali documentate o intensità
temporali specifiche per ottenere un segnale informativo distinto dall'output.

## Output

- `outputs/economic_sector_path.csv`: output settoriale estratto dal solver;
- `outputs/ecological_summary.csv`: pressioni per inquinante, anno e modalità;
- `outputs/ecological_contributions.csv`: contributi settore-inquinante;
- `outputs/physical_ecological_summary.csv`: masse fisiche aggregate;
- `outputs/physical_ecological_contributions.csv`: masse fisiche per settore;
- `outputs/mapping_coverage.csv`: copertura del raccordo settoriale;
- `outputs/dashboard.json`: dataset del cruscotto;
- `outputs/VALIDATION_REPORT.json`: invarianza della sorgente e confronti numerici;
- `outputs/SOURCE_MANIFEST_BEFORE.json` e `SOURCE_MANIFEST_AFTER.json`.

Per controllare un pacchetto già elaborato senza rieseguire il solver:

```bash
python verify_companion.py
```
