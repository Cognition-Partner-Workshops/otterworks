      *----------------------------------------------------------------*
      * FLASGU   ASSIGNMENT UNLOAD RECORD               LRECL 064 FB   *
      *----------------------------------------------------------------*
       01  FLASGU-REC.
           05  AU-ASGID              PIC X(10).
           05  AU-EMPID              PIC X(8).
           05  AU-EMP-DBKEY          PIC 9(10).
           05  AU-VEHID              PIC X(8).
           05  AU-STRT               PIC 9(8).
           05  AU-END                PIC 9(8).
           05  AU-RSN                PIC X(2).
           05  FILLER                PIC X(10).
