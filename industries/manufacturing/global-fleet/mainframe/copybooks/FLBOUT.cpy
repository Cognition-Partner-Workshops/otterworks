      *----------------------------------------------------------------*
      * FLBOUT   BENEFIT RUN OUTPUT (BENOUT)            LRECL 064 FB   *
      *----------------------------------------------------------------*
       01  FLBOUT-REC.
           05  BO-PERIOD             PIC 9(6).
           05  BO-EMPID              PIC X(8).
           05  BO-EMP-DBKEY          PIC 9(10).
           05  BO-VEHID              PIC X(8).
           05  BO-DAYS               PIC 9(2).
           05  BO-TAXB               PIC S9(7)V99 COMP-3.
           05  BO-MILES              PIC 9(6).
           05  BO-MREIM              PIC S9(7)V99 COMP-3.
           05  BO-FLAG               PIC X(1).
           05  FILLER                PIC X(13).
