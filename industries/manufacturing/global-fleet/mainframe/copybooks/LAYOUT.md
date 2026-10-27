# Unload layouts

Derived the same way as `migration/source/copybooks/FIELD-DERIVATION.md`: the copybook gives the order and PIC of each field, the PIC gives the byte width, and the offsets are the running sum. `COMP-3` packs two digits per byte plus a sign nibble, so `S9(n)V99 COMP-3` is `ceil((n+2+1)/2)` bytes. Text is ASCII. Dates are `YYYYMMDD`, with `00000000` meaning none.

The unload writes the owner's CALC key and db-key alongside each member record, because a flat file has no sets. `*-DBKEY` is the IDMS db-key (page × 256 + line) and is the only field that tells two occurrences with the same CALC key apart.

## FLEMPU, `EMPLOYEE.dat`, LRECL 100

| Offset | Len | Field | PIC | Notes |
|---:|---:|---|---|---|
| 0 | 10 | EU-DBKEY | 9(10) | |
| 10 | 8 | EU-EMPID | X(8) | CALC key |
| 18 | 20 | EU-SURN | X(20) | |
| 38 | 15 | EU-FORN | X(15) | |
| 53 | 2 | EU-GRD | 9(2) | 01 to 12 |
| 55 | 6 | EU-CC | X(6) | cost centre |
| 61 | 8 | EU-HIRE | 9(8) | |
| 69 | 8 | EU-LEAV | 9(8) | |
| 77 | 1 | EU-STAT | X(1) | A active, T terminated, X transferred abroad |
| 78 | 4 | EU-CNTRB | S9(5)V99 COMP-3 | monthly employee contribution |
| 82 | 4 | EU-LOC | X(4) | |
| 86 | 14 | FILLER | | |

## FLVEHU, `VEHICLE.dat`, LRECL 100

| Offset | Len | Field | PIC | Notes |
|---:|---:|---|---|---|
| 0 | 10 | VU-DBKEY | 9(10) | |
| 10 | 8 | VU-VEHID | X(8) | CALC key |
| 18 | 8 | VU-PLATE | X(8) | registration mark |
| 26 | 12 | VU-MAKE | X(12) | |
| 38 | 16 | VU-MODL | X(16) | |
| 54 | 5 | VU-LIST | S9(7)V99 COMP-3 | list price |
| 59 | 3 | VU-CO2 | 9(3) | g/km |
| 62 | 4 | VU-BPCT | 9(2)V99 | appropriate percentage |
| 66 | 1 | VU-FUEL | X(1) | P D H E |
| 67 | 8 | VU-REGD | 9(8) | |
| 75 | 8 | VU-OWNR-EMPID | X(8) | owner in EMP-VEHICLE |
| 83 | 10 | VU-OWNR-DBKEY | 9(10) | |
| 93 | 7 | FILLER | | |

## FLASGU, `ASSIGNMENT.dat`, LRECL 64

| Offset | Len | Field | PIC | Notes |
|---:|---:|---|---|---|
| 0 | 10 | AU-ASGID | X(10) | |
| 10 | 8 | AU-EMPID | X(8) | owner in EMP-ASSIGN |
| 18 | 10 | AU-EMP-DBKEY | 9(10) | |
| 28 | 8 | AU-VEHID | X(8) | owner in VEH-ASSIGN |
| 36 | 8 | AU-STRT | 9(8) | |
| 44 | 8 | AU-END | 9(8) | |
| 52 | 2 | AU-RSN | X(2) | NC new car, RP replacement, PL pool loan |
| 54 | 10 | FILLER | | |

## FLMCLU, `MILECLM.dat`, LRECL 64

| Offset | Len | Field | PIC | Notes |
|---:|---:|---|---|---|
| 0 | 10 | MU-CLMID | X(10) | |
| 10 | 8 | MU-EMPID | X(8) | owner in EMP-CLAIM |
| 18 | 10 | MU-EMP-DBKEY | 9(10) | |
| 28 | 8 | MU-VEHID | X(8) | |
| 36 | 8 | MU-DATE | 9(8) | |
| 44 | 5 | MU-MILES | 9(5) | |
| 49 | 1 | MU-STAT | X(1) | A approved, P pending, R rejected |
| 50 | 10 | MU-PURP | X(10) | |
| 60 | 4 | FILLER | | |

## FLBPDU, `BENPRD.dat`, LRECL 40

| Offset | Len | Field | PIC | Notes |
|---:|---:|---|---|---|
| 0 | 6 | PU-PERIOD | 9(6) | YYYYMM, CALC key |
| 6 | 8 | PU-STRT | 9(8) | |
| 14 | 8 | PU-END | 9(8) | |
| 22 | 4 | PU-MRATE | 9V999 | pounds per mile |
| 26 | 1 | PU-STAT | X(1) | O open, C closed |
| 27 | 8 | PU-RUNDT | 9(8) | |
| 35 | 5 | FILLER | | |

## FLBOUT, `BENOUT.dat`, LRECL 64

| Offset | Len | Field | PIC | Notes |
|---:|---:|---|---|---|
| 0 | 6 | BO-PERIOD | 9(6) | |
| 6 | 8 | BO-EMPID | X(8) | |
| 14 | 10 | BO-EMP-DBKEY | 9(10) | |
| 24 | 8 | BO-VEHID | X(8) | spaces when only mileage was paid |
| 32 | 2 | BO-DAYS | 9(2) | days the car was available in the period |
| 34 | 5 | BO-TAXB | S9(7)V99 COMP-3 | taxable benefit for the period |
| 39 | 6 | BO-MILES | 9(6) | approved business miles |
| 45 | 5 | BO-MREIM | S9(7)V99 COMP-3 | mileage reimbursed |
| 50 | 1 | BO-FLAG | X(1) | L leaver in period |
| 51 | 13 | FILLER | | |

`BENRPT.txt` is the SYSOUT print of the same run.
