# Rapporto di validazione della distribuzione autonoma

## Motore incorporato

- repository: `redplanetcitizen/NewHarmony_Milestone_F_Corrected`;
- commit: `d71a68c6f02cde756ed814b8e209b23177ab56e0`;
- file operativi incorporati: 128;
- file incorporati identici alla sorgente: 128/128;
- firma operativa dell'albero `engine/`:
  `e376d36cfddb46d54a9d98157244fe2fd11fc62c48e7456096c677ed6309ce1c`;
- firma prima e dopo l'esecuzione: identica;
- modifiche al solver: nessuna.

## Riproduzione dei risultati

- modalità rieseguite: `frozen` e `historical`;
- anni computazionali per modalità: 8;
- grandezze confrontate per anno: 6;
- controlli numerici complessivi: 96;
- controlli superati: 96.

## Estensione ecologica

- output economici settore-anno: 1.136;
- inquinanti: 55;
- inquinanti con coefficienti fisici: 49/55;
- masse fisiche settore–inquinante esportate: 51.744;
- settori mappati: 66/71;
- copertura dell'output lordo: 87,37–89,69%;
- modalità: associazioni qualitative e masse fisiche dirette ex post;
- retroazione sul solver: nessuna.

## Integrazione del selettore settoriale

- settori presentati nel selettore: 71;
- settori ecologicamente raccordati: 66;
- settori non raccordati esplicitamente marcati: 5;
- Harmony diagnostica e copertura del fabbisogno-obiettivo disponibili per ogni settore e anno;
- associazioni qualitative mai rappresentate come quantità;
- semaforo settoriale disabilitato (`n.d.`) in assenza di soglie documentate;
- viste verificate: aggregata, settore raccordato, selezione incrociata
  settore–inquinante e settore non raccordato;
- errori JavaScript rilevati nel test locale: 0.

## Autonomia

Il test conclusivo è stato eseguito usando esclusivamente `engine/` all'interno
della distribuzione. Non è stato effettuato alcun clone, download di dati o
accesso al repository durante la soluzione. La connessione Internet è richiesta
soltanto dall'installazione iniziale di NumPy e SciPy, se non già disponibili.
