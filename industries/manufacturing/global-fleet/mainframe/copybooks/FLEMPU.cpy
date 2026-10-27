      *----------------------------------------------------------------*
      * FLEMPU   EMPLOYEE UNLOAD RECORD                 LRECL 100 FB   *
      *----------------------------------------------------------------*
       01  FLEMPU-REC.
           05  EU-DBKEY              PIC 9(10).
           05  EU-EMPID              PIC X(8).
           05  EU-SURN               PIC X(20).
           05  EU-FORN               PIC X(15).
           05  EU-GRD                PIC 9(2).
           05  EU-CC                 PIC X(6).
           05  EU-HIRE               PIC 9(8).
           05  EU-LEAV               PIC 9(8).
           05  EU-STAT               PIC X(1).
           05  EU-CNTRB              PIC S9(5)V99 COMP-3.
           05  EU-LOC                PIC X(4).
           05  FILLER                PIC X(14).
