      * RATEOUT  LRECL 80  - one rated policy
      * OUT-STATUS  OK  | DEC (declined) | REJ (rejected)
      * OUT-FACTOR-SRC  T territory row, D default territory, O override
       01  OUT-REC.
           05  OUT-POL-ID          PIC X(8).
           05  OUT-STATUS          PIC X(3).
           05  OUT-REASON          PIC X(4).
           05  OUT-BASE-RATE       PIC 9(5)V9(4).
           05  OUT-TERR-FACTOR     PIC 9V999.
           05  OUT-FACTOR-SRC      PIC X.
           05  OUT-BASE-PREM       PIC S9(9)V99.
           05  OUT-MOD-PREM        PIC S9(9)V99.
           05  OUT-MIN-FLAG        PIC X.
           05  OUT-FEE             PIC 9(3)V99.
           05  OUT-TOTAL           PIC S9(9)V99.
           05  FILLER              PIC X(12).
