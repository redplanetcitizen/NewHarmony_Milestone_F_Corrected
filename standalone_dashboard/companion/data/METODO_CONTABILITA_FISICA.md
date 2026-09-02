# Metodo della contabilità fisica

La matrice `coefficienti_ecologici_fisici_72x55.csv` contiene coefficienti
diretti in kg per milione di dollari 2012. Il motore Milestone F Corrected
produce invece quantità reali valutate a prezzi 2019. I due importi monetari
non vengono mai moltiplicati direttamente.

Per il settore ecologico `e`, raccordato al settore F `s`, e l'inquinante
`p`, il companion calcola:

`massa(e,p,t) = coefficiente(e,p,2012) × output(e,2012) × [output_F(s,t) / output_osservato_F(s,2019)]`.

Il termine fra parentesi è un rapporto adimensionale di attività reale. Nei
casi in cui un settore F corrisponde a più settori ecologici, ogni settore
figlio conserva il proprio output di base 2012 e segue il rapporto di attività
del settore F padre.

Le celle vuote della matrice significano dato non disponibile, non zero. I sei
inquinanti senza alcun coefficiente sono: `FGAS`, `CHL_SOLV`, `PATH`, `THERM`,
`SILICA` e `PHARMA`.

Le intensità sono mantenute costanti. Per questo il semaforo relativo al
singolo settore non è calcolato: richiederebbe soglie documentate specifiche o
intensità variabili nel tempo. Il semaforo aggregato misura soltanto la
variazione della massa totale rispetto al 2019 e non la pericolosità.

La Harmony settoriale mostrata nel cruscotto è diagnostica. Si applica la
funzione `H(r)=r/(1,1+r)` a `r = output lordo realizzato / fabbisogno lordo
sociale e di investimento`. Non sostituisce né modifica la Harmony globale del
solver.
