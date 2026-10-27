      *----------------------------------------------------------------*
      * FLMCLU   MILEAGE-CLAIM UNLOAD RECORD            LRECL 064 FB   *
      *----------------------------------------------------------------*
       01  FLMCLU-REC.
           05  MU-CLMID              PIC X(10).
           05  MU-EMPID              PIC X(8).
           05  MU-EMP-DBKEY          PIC 9(10).
           05  MU-VEHID              PIC X(8).
           05  MU-DATE               PIC 9(8).
           05  MU-MILES              PIC 9(5).
           05  MU-STAT               PIC X(1).
           05  MU-PURP               PIC X(10).
           05  FILLER                PIC X(4).
