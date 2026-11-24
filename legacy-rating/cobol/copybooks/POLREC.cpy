      * POLREC  LRECL 80  - policy submitted for rating
      * Signed fields carry the sign in the last digit (overpunch).
       01  POL-REC.
           05  POL-ID              PIC X(8).
           05  POL-LINE            PIC X(2).
           05  POL-STATE           PIC X(2).
           05  POL-CLASS           PIC X(5).
           05  POL-TERR            PIC X(3).
           05  POL-EFF-DATE        PIC 9(8).
           05  POL-EXPOSURE        PIC S9(7)V99.
           05  POL-YRS-IN-BUS      PIC 9(2).
           05  POL-CLAIMS-3YR      PIC 9(2).
           05  POL-DEDUCT          PIC 9(5).
           05  POL-MULTI-POL       PIC X.
           05  POL-SCHED-MOD       PIC S9V99.
           05  POL-ADDL-INSD       PIC 9(2).
           05  POL-ENDT-EQUIP      PIC X.
           05  POL-ENDT-WAIVER     PIC X.
           05  POL-ENDT-HNOA       PIC X.
           05  FILLER              PIC X(25).
