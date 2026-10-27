      *----------------------------------------------------------------*
      * FLBPDU   BENEFIT-PERIOD UNLOAD RECORD           LRECL 040 FB   *
      *----------------------------------------------------------------*
       01  FLBPDU-REC.
           05  PU-PERIOD             PIC 9(6).
           05  PU-STRT               PIC 9(8).
           05  PU-END                PIC 9(8).
           05  PU-MRATE              PIC 9V999.
           05  PU-STAT               PIC X(1).
           05  PU-RUNDT              PIC 9(8).
           05  FILLER                PIC X(5).
