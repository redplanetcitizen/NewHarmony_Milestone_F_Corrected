# Validazione della prima fase

Sorgente verificata: `redplanetcitizen/NewHarmony_Milestone_F_Corrected`,
commit `d71a68c6f02cde756ed814b8e209b23177ab56e0`.

## Invarianza

- file della sorgente controllati: 130;
- firma SHA-256 prima dell'esecuzione:
  `291a58d76acda2e9c9b947ee42d01c0c76a627d6f07b6183900b14cb163fbfc5`;
- firma dopo l'esecuzione: identica;
- stato Git dopo l'esecuzione: pulito;
- bytecode e output nella sorgente: non prodotti.

## Confronto numerico

La riesecuzione esterna dei due percorsi finali è stata confrontata con i file
`results/F_final/{frozen,historical}/annual_path.csv` del repository. Sono
stati verificati soddisfacimento, Harmony, investimento, stock iniziale, stock
finale e output lordo per tutti gli otto anni computazionali:

- confronti eseguiti: 96;
- confronti superati: 96;
- modifiche al solver: nessuna.

## Contabilità ecologica

- modalità qualitative: categorie 0/1/2, mai trattate come quantità;
- modalità fisica: coefficienti diretti kg/MUSD 2012 con riscalamento per rapporto di attività reale 2019;
- settori del motore: 71;
- settori mappati: 66;
- settori pubblici non mappati: 5;
- inquinanti: 55;
- output settoriali estratti: 1.136;
- inquinanti con coefficienti fisici disponibili: 49 su 55;
- inquinanti privi di coefficienti: 6, mostrati come non disponibili;
- copertura dell'output lordo: fra 87,37% e 89,69% secondo anno e modalità.

La copertura mancante è mostrata esplicitamente nel cruscotto e non viene
colmata mediante attribuzioni arbitrarie.

## Selettore settoriale del cruscotto

- settori economici selezionabili: 71;
- settori con raccordo ecologico: 66;
- settori senza raccordo: 5, mantenuti selezionabili e marcati `n.d.`;
- contributi completi esportati nel payload: 13.808;
- vista `Tutti i settori`: invariata, con graduatoria dei dieci contributori;
- vista settoriale economica: copertura percentuale del fabbisogno lordo e
  Harmony diagnostica anno per anno;
- vista fisica: massa diretta in kg/tonnellate e profilo dei dieci inquinanti
  principali;
- vista qualitativa: sole categorie `operativa` e `caratteristica`, senza
  grafico quantitativo;
- segnale verde/giallo/arancione/rosso: variazione della sola massa aggregata
  rispetto al 2019; sul singolo settore resta `n.d.` in assenza di soglie
  documentate.

Sono stati provati nel browser locale un settore raccordato, il passaggio
incrociato settore→inquinante e un settore pubblico non raccordato. Non sono
stati rilevati errori JavaScript.
