# Handoff per lo sviluppatore

## Obiettivo

La distribuzione combina Milestone F Corrected con una contabilità ecologica
ex post e un cruscotto, mantenendo un confine rigido fra motore e integrazione.

```text
engine/ (sola lettura)
   │
   └─ solve_lexicographic_lp()
          │ risultati in memoria
          ▼
companion/eco_companion/adapter.py
          │ pannello anno × settore + diagnostica del fabbisogno
          ├─ companion/eco_companion/accounting.py (associazioni 0/1/2)
          └─ companion/eco_companion/physical_accounting.py (masse in kg)
          │
          ├─ outputs/*.csv e *.json
          └─ companion/dashboard/data.json
```

## Contratto di integrazione

`adapter.solve_final_paths()` carica il codice originale da `engine/code/` con
la scrittura del bytecode disabilitata. Non invoca `run_all()`, perché quella
funzione scriverebbe nella cartella `engine/results/`; richiama invece le
funzioni di soluzione e conserva gli oggetti risultanti in memoria.

Il pannello economico normalizzato contiene:

- `technology_mode`;
- `year`;
- `published`;
- `sector_index`;
- `bea_code`;
- `sector_name`;
- `gross_output_real_musd`.
- `observed_gross_output_2019_real_musd`;
- `gross_requirement_target_real_musd`;
- `gross_requirement_coverage`;
- `diagnostic_sector_harmony`.

La contabilità ecologica deve continuare a dipendere soltanto da questo
contratto, non dagli oggetti interni del solver.

## Raccordo settoriale

`companion/data/crosswalk_f71_to_eco72.csv` è una decisione metodologica
esplicita. Non sostituire i cinque settori `unmapped` con proxy senza una fonte
documentata. Le righe `equal-share proxy` sono punti naturali per un futuro
miglioramento mediante quote empiriche.

## Regola di non regressione

Ogni modifica deve preservare simultaneamente:

1. l'identità degli hash elencati in `ENGINE_INTEGRITY.json`;
2. 96/96 confronti con i risultati aggregati pubblicati;
3. assenza di file nuovi in `engine/` dopo l'esecuzione;
4. indice fisico aggregato di base 2019 uguale a 100 per ciascun inquinante disponibile;
5. separazione visibile fra associazioni qualitative e masse fisiche;
6. assenza di un semaforo settoriale finché non esistono soglie documentate.

Il payload del cruscotto comprende inoltre `sectors`, `sector_economy`,
`qualitative_associations` e `physical_sector_contributions`. Il selettore deve continuare a mostrare anche i settori
non raccordati, senza sostituire il valore ecologico mancante con zero.

## Evoluzioni previste

- sostituire le quote paritarie del raccordo con quote empiriche documentate;
- sostituire le intensità fisiche 2012 costanti con serie temporali documentate;
- introdurre soglie ambientali settoriali soltanto quando esiste una fonte verificabile;
- estendere i test automatici dell'interazione nel browser;
- soltanto in una fase separata valutare vincoli ecologici endogeni. Tale fase
  cambierebbe il problema di ottimizzazione e non appartiene a questo companion.
