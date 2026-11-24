      ******************************************************************
      * RATEPREM - nightly premium rating batch.
      *
      * Input : RATEPREM_POLICIES - POLREC records, one per line
      *         RATEPREM_TABLES   - directory holding the rating tables
      *                             (class, territory, eligibility,
      *                              minimum premium, dated overrides)
      * Output: RATEPREM_OUT      - RATEOUT records, one per policy
      *         stdout            - "RATEPREM READ=n OK=n DEC=n REJ=n"
      * RC    : 0 ok, 12 I/O error
      ******************************************************************
       IDENTIFICATION DIVISION.
       PROGRAM-ID. RATEPREM.

       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT POLICY-FILE ASSIGN TO WS-POL-PATH
               ORGANIZATION IS LINE SEQUENTIAL
               FILE STATUS IS WS-POL-STATUS.
           SELECT RATED-FILE ASSIGN TO WS-OUT-PATH
               ORGANIZATION IS LINE SEQUENTIAL
               FILE STATUS IS WS-OUT-STATUS.
           SELECT TABLE-FILE ASSIGN TO WS-TBL-PATH
               ORGANIZATION IS LINE SEQUENTIAL
               FILE STATUS IS WS-TBL-STATUS.

       DATA DIVISION.
       FILE SECTION.
       FD  POLICY-FILE.
           COPY POLREC.
       FD  RATED-FILE.
           COPY RATEOUT.
       FD  TABLE-FILE.
       01  TBL-LINE                PIC X(120).

       WORKING-STORAGE SECTION.
       01  WS-POL-PATH             PIC X(256).
       01  WS-OUT-PATH             PIC X(256).
       01  WS-TBL-DIR              PIC X(256).
       01  WS-TBL-PATH             PIC X(256).
       01  WS-POL-STATUS           PIC XX.
       01  WS-OUT-STATUS           PIC XX.
       01  WS-TBL-STATUS           PIC XX.
       01  WS-EOF                  PIC X VALUE 'N'.
       01  WS-TBL-EOF              PIC X VALUE 'N'.
       01  WS-TBL-NAME             PIC X(32).

       01  WS-F1                   PIC X(16).
       01  WS-F2                   PIC X(16).
       01  WS-F3                   PIC X(16).
       01  WS-F4                   PIC X(16).
       01  WS-F5                   PIC X(16).
       01  WS-F6                   PIC X(16).

           COPY RATETBL.

       01  WS-COUNTS.
           05  WS-READ             PIC 9(7) VALUE 0.
           05  WS-OK               PIC 9(7) VALUE 0.
           05  WS-DEC              PIC 9(7) VALUE 0.
           05  WS-REJ              PIC 9(7) VALUE 0.
       01  WS-I                    PIC 9(3).
       01  WS-FOUND                PIC X.
       01  WS-RATE                 PIC 9(5)V9(4).
       01  WS-FACTOR               PIC 9V999.
       01  WS-EXP-MOD              PIC 9V99.
       01  WS-DED-FACTOR           PIC 9V99.
       01  WS-SCHED                PIC S9V99.
       01  WS-WIND-FACTOR          PIC 9V999.
       01  WS-MINIMUM              PIC 9(7)V99.
       01  WS-STEP                 PIC S9(9)V99.
       01  WS-BASE                 PIC S9(9)V99.
       01  WS-PREM                 PIC S9(9)V99.
       01  WS-POLICY-FEE           PIC 9(3)V99 VALUE 35.00.

       PROCEDURE DIVISION.
       0000-MAIN.
           ACCEPT WS-POL-PATH FROM ENVIRONMENT 'RATEPREM_POLICIES'
           ACCEPT WS-OUT-PATH FROM ENVIRONMENT 'RATEPREM_OUT'
           ACCEPT WS-TBL-DIR  FROM ENVIRONMENT 'RATEPREM_TABLES'
           PERFORM 0100-LOAD-TABLES
           OPEN INPUT POLICY-FILE
           IF WS-POL-STATUS NOT = '00'
               DISPLAY 'RATEPREM E: cannot open policies '
                   WS-POL-STATUS UPON SYSERR
               MOVE 12 TO RETURN-CODE
               STOP RUN
           END-IF
           OPEN OUTPUT RATED-FILE
           IF WS-OUT-STATUS NOT = '00'
               DISPLAY 'RATEPREM E: cannot open output '
                   WS-OUT-STATUS UPON SYSERR
               MOVE 12 TO RETURN-CODE
               STOP RUN
           END-IF
           PERFORM UNTIL WS-EOF = 'Y'
               READ POLICY-FILE
                   AT END MOVE 'Y' TO WS-EOF
                   NOT AT END PERFORM 1000-RATE-POLICY
               END-READ
           END-PERFORM
           CLOSE POLICY-FILE RATED-FILE
           DISPLAY 'RATEPREM READ=' WS-READ ' OK=' WS-OK
               ' DEC=' WS-DEC ' REJ=' WS-REJ
           MOVE 0 TO RETURN-CODE
           STOP RUN.

       0100-LOAD-TABLES.
           MOVE 'class-factors.dat' TO WS-TBL-NAME
           PERFORM 0110-OPEN-TABLE
           PERFORM UNTIL WS-TBL-EOF = 'Y'
               PERFORM 0120-NEXT-ROW
               IF WS-TBL-EOF = 'N'
                   ADD 1 TO CT-COUNT
                   MOVE WS-F1 TO CT-LINE (CT-COUNT)
                   MOVE WS-F2 TO CT-CLASS (CT-COUNT)
                   COMPUTE CT-RATE (CT-COUNT) = FUNCTION NUMVAL(WS-F3)
                   COMPUTE CT-FROM (CT-COUNT) = FUNCTION NUMVAL(WS-F4)
                   PERFORM 0130-OPEN-END-DATE
                   MOVE WS-F6 TO CT-TO (CT-COUNT)
               END-IF
           END-PERFORM
           CLOSE TABLE-FILE

           MOVE 'territory-factors.dat' TO WS-TBL-NAME
           PERFORM 0110-OPEN-TABLE
           PERFORM UNTIL WS-TBL-EOF = 'Y'
               PERFORM 0120-NEXT-ROW
               IF WS-TBL-EOF = 'N'
                   ADD 1 TO TT-COUNT
                   MOVE WS-F1 TO TT-LINE (TT-COUNT)
                   MOVE WS-F2 TO TT-TERR (TT-COUNT)
                   COMPUTE TT-FACTOR (TT-COUNT) =
                       FUNCTION NUMVAL(WS-F3)
                   COMPUTE TT-FROM (TT-COUNT) = FUNCTION NUMVAL(WS-F4)
                   PERFORM 0130-OPEN-END-DATE
                   MOVE WS-F6 TO TT-TO (TT-COUNT)
               END-IF
           END-PERFORM
           CLOSE TABLE-FILE

           MOVE 'line-eligibility.dat' TO WS-TBL-NAME
           PERFORM 0110-OPEN-TABLE
           PERFORM UNTIL WS-TBL-EOF = 'Y'
               PERFORM 0120-NEXT-ROW
               IF WS-TBL-EOF = 'N'
                   ADD 1 TO ET-COUNT
                   MOVE WS-F1 TO ET-LINE (ET-COUNT)
                   MOVE WS-F2 TO ET-CLASS (ET-COUNT)
                   MOVE WS-F3 TO ET-STATE (ET-COUNT)
                   MOVE WS-F4 TO ET-ELIG (ET-COUNT)
                   MOVE WS-F5 TO ET-REASON (ET-COUNT)
               END-IF
           END-PERFORM
           CLOSE TABLE-FILE

           MOVE 'minimum-premium.dat' TO WS-TBL-NAME
           PERFORM 0110-OPEN-TABLE
           PERFORM UNTIL WS-TBL-EOF = 'Y'
               PERFORM 0120-NEXT-ROW
               IF WS-TBL-EOF = 'N'
                   ADD 1 TO MT-COUNT
                   MOVE WS-F1 TO MT-LINE (MT-COUNT)
                   MOVE WS-F2 TO MT-STATE (MT-COUNT)
                   COMPUTE MT-MINIMUM (MT-COUNT) =
                       FUNCTION NUMVAL(WS-F3)
               END-IF
           END-PERFORM
           CLOSE TABLE-FILE

           MOVE 'overrides.dat' TO WS-TBL-NAME
           PERFORM 0110-OPEN-TABLE
           PERFORM UNTIL WS-TBL-EOF = 'Y'
               PERFORM 0120-NEXT-ROW
               IF WS-TBL-EOF = 'N'
                   ADD 1 TO OT-COUNT
                   MOVE WS-F1 TO OT-LINE (OT-COUNT)
                   MOVE WS-F2 TO OT-CLASS (OT-COUNT)
                   MOVE WS-F3 TO OT-TERR (OT-COUNT)
                   COMPUTE OT-FACTOR (OT-COUNT) =
                       FUNCTION NUMVAL(WS-F4)
                   COMPUTE OT-FROM (OT-COUNT) = FUNCTION NUMVAL(WS-F5)
                   MOVE WS-F6 TO WS-F5
                   PERFORM 0130-OPEN-END-DATE
                   MOVE WS-F6 TO OT-TO (OT-COUNT)
               END-IF
           END-PERFORM
           CLOSE TABLE-FILE.

       0110-OPEN-TABLE.
           MOVE SPACES TO WS-TBL-PATH
           STRING FUNCTION TRIM(WS-TBL-DIR) '/'
               FUNCTION TRIM(WS-TBL-NAME)
               DELIMITED BY SIZE INTO WS-TBL-PATH
           MOVE 'N' TO WS-TBL-EOF
           OPEN INPUT TABLE-FILE
           IF WS-TBL-STATUS NOT = '00'
               DISPLAY 'RATEPREM E: cannot open table '
                   FUNCTION TRIM(WS-TBL-PATH) UPON SYSERR
               MOVE 12 TO RETURN-CODE
               STOP RUN
           END-IF.

      * Skip comment lines (first column '*') and blank lines.
       0120-NEXT-ROW.
           MOVE SPACES TO TBL-LINE
           PERFORM WITH TEST AFTER
                   UNTIL WS-TBL-EOF = 'Y'
                      OR (TBL-LINE (1:1) NOT = '*'
                          AND TBL-LINE NOT = SPACES)
               READ TABLE-FILE
                   AT END MOVE 'Y' TO WS-TBL-EOF
               END-READ
           END-PERFORM
           IF WS-TBL-EOF = 'N'
               MOVE SPACES TO WS-F1 WS-F2 WS-F3 WS-F4 WS-F5 WS-F6
               UNSTRING TBL-LINE DELIMITED BY '|'
                   INTO WS-F1 WS-F2 WS-F3 WS-F4 WS-F5 WS-F6
               END-UNSTRING
           END-IF.

      * An empty end date means the row stays in force.
       0130-OPEN-END-DATE.
           IF WS-F5 = SPACES
               MOVE '99999999' TO WS-F6
           ELSE
               MOVE WS-F5 TO WS-F6
           END-IF.

       1000-RATE-POLICY.
           ADD 1 TO WS-READ
           MOVE SPACES TO OUT-REC
           MOVE POL-ID TO OUT-POL-ID
           MOVE 'OK ' TO OUT-STATUS
           MOVE ZERO TO OUT-BASE-RATE OUT-TERR-FACTOR OUT-BASE-PREM
                        OUT-MOD-PREM OUT-FEE OUT-TOTAL
           MOVE 'N' TO OUT-MIN-FLAG
           PERFORM 1100-VALIDATE-LINE
           IF OUT-STATUS = 'OK '
               PERFORM 1200-VALIDATE-EXPOSURE
           END-IF
           IF OUT-STATUS = 'OK '
               PERFORM 2000-CHECK-ELIGIBILITY
           END-IF
           IF OUT-STATUS = 'OK '
               PERFORM 2100-LOOKUP-CLASS
           END-IF
           IF OUT-STATUS = 'OK '
               PERFORM 2200-LOOKUP-TERRITORY
           END-IF
           IF OUT-STATUS = 'OK '
               PERFORM 2300-LOOKUP-OVERRIDE
               PERFORM 3000-BASE-PREMIUM
               PERFORM 3100-EXPERIENCE-MOD
               PERFORM 3200-DEDUCTIBLE-CREDIT
               PERFORM 3300-SCHEDULE-MOD
               PERFORM 3400-MULTI-POLICY
               PERFORM 3450-WIND-SURCHARGE
               PERFORM 3500-MINIMUM-PREMIUM
               PERFORM 3600-POLICY-FEE
           END-IF
           EVALUATE OUT-STATUS
               WHEN 'OK ' ADD 1 TO WS-OK
               WHEN 'DEC' ADD 1 TO WS-DEC
               WHEN OTHER ADD 1 TO WS-REJ
           END-EVALUATE
           WRITE OUT-REC
           IF WS-OUT-STATUS NOT = '00'
               DISPLAY 'RATEPREM E: cannot write output '
                   WS-OUT-STATUS UPON SYSERR
               MOVE 12 TO RETURN-CODE
               STOP RUN
           END-IF.

       1100-VALIDATE-LINE.
           IF POL-LINE NOT = 'GL' AND POL-LINE NOT = 'PR'
              AND POL-LINE NOT = 'CA'
               MOVE 'REJ' TO OUT-STATUS
               MOVE 'LN' TO OUT-REASON
           END-IF.

       1200-VALIDATE-EXPOSURE.
           IF POL-EXPOSURE NOT > ZERO
               MOVE 'REJ' TO OUT-STATUS
               MOVE 'EX' TO OUT-REASON
           END-IF.

      * A row for the policy's state wins over the all-states row.
      * A class with no row at all is eligible.
       2000-CHECK-ELIGIBILITY.
           MOVE 'N' TO WS-FOUND
           PERFORM VARYING WS-I FROM 1 BY 1
                   UNTIL WS-I > ET-COUNT OR WS-FOUND = 'Y'
               IF ET-LINE (WS-I) = POL-LINE
                  AND ET-CLASS (WS-I) = POL-CLASS
                  AND ET-STATE (WS-I) = POL-STATE
                   MOVE 'Y' TO WS-FOUND
                   PERFORM 2010-APPLY-ELIGIBILITY
               END-IF
           END-PERFORM
           PERFORM VARYING WS-I FROM 1 BY 1
                   UNTIL WS-I > ET-COUNT OR WS-FOUND = 'Y'
               IF ET-LINE (WS-I) = POL-LINE
                  AND ET-CLASS (WS-I) = POL-CLASS
                  AND ET-STATE (WS-I) = '**'
                   MOVE 'Y' TO WS-FOUND
                   PERFORM 2010-APPLY-ELIGIBILITY
               END-IF
           END-PERFORM.

       2010-APPLY-ELIGIBILITY.
           IF ET-ELIG (WS-I) = 'N'
               MOVE 'DEC' TO OUT-STATUS
               MOVE ET-REASON (WS-I) TO OUT-REASON
           END-IF.

       2100-LOOKUP-CLASS.
           MOVE 'N' TO WS-FOUND
           PERFORM VARYING WS-I FROM 1 BY 1
                   UNTIL WS-I > CT-COUNT OR WS-FOUND = 'Y'
               IF CT-LINE (WS-I) = POL-LINE
                  AND CT-CLASS (WS-I) = POL-CLASS
                  AND CT-FROM (WS-I) <= POL-EFF-DATE
                  AND CT-TO (WS-I) >= POL-EFF-DATE
                   MOVE 'Y' TO WS-FOUND
                   MOVE CT-RATE (WS-I) TO WS-RATE
               END-IF
           END-PERFORM
           IF WS-FOUND = 'N'
               MOVE 'REJ' TO OUT-STATUS
               MOVE 'CL' TO OUT-REASON
           ELSE
               MOVE WS-RATE TO OUT-BASE-RATE
           END-IF.

      * A territory with no row in force falls back to territory 000.
       2200-LOOKUP-TERRITORY.
           MOVE 'N' TO WS-FOUND
           PERFORM VARYING WS-I FROM 1 BY 1
                   UNTIL WS-I > TT-COUNT OR WS-FOUND = 'Y'
               IF TT-LINE (WS-I) = POL-LINE
                  AND TT-TERR (WS-I) = POL-TERR
                  AND TT-FROM (WS-I) <= POL-EFF-DATE
                  AND TT-TO (WS-I) >= POL-EFF-DATE
                   MOVE 'Y' TO WS-FOUND
                   MOVE TT-FACTOR (WS-I) TO WS-FACTOR
                   MOVE 'T' TO OUT-FACTOR-SRC
               END-IF
           END-PERFORM
           PERFORM VARYING WS-I FROM 1 BY 1
                   UNTIL WS-I > TT-COUNT OR WS-FOUND = 'Y'
               IF TT-LINE (WS-I) = POL-LINE
                  AND TT-TERR (WS-I) = '000'
                  AND TT-FROM (WS-I) <= POL-EFF-DATE
                  AND TT-TO (WS-I) >= POL-EFF-DATE
                   MOVE 'Y' TO WS-FOUND
                   MOVE TT-FACTOR (WS-I) TO WS-FACTOR
                   MOVE 'D' TO OUT-FACTOR-SRC
               END-IF
           END-PERFORM
           IF WS-FOUND = 'N'
               MOVE 'REJ' TO OUT-STATUS
               MOVE 'TR' TO OUT-REASON
           END-IF.

      * An override replaces the territory factor; it never stacks.
       2300-LOOKUP-OVERRIDE.
           MOVE 'N' TO WS-FOUND
           PERFORM VARYING WS-I FROM 1 BY 1
                   UNTIL WS-I > OT-COUNT OR WS-FOUND = 'Y'
               IF OT-LINE (WS-I) = POL-LINE
                  AND OT-CLASS (WS-I) = POL-CLASS
                  AND OT-TERR (WS-I) = POL-TERR
                  AND OT-FROM (WS-I) <= POL-EFF-DATE
                  AND OT-TO (WS-I) >= POL-EFF-DATE
                   MOVE 'Y' TO WS-FOUND
                   MOVE OT-FACTOR (WS-I) TO WS-FACTOR
                   MOVE 'O' TO OUT-FACTOR-SRC
               END-IF
           END-PERFORM
           MOVE WS-FACTOR TO OUT-TERR-FACTOR.

       3000-BASE-PREMIUM.
           COMPUTE WS-STEP ROUNDED = POL-EXPOSURE * WS-RATE
           COMPUTE WS-BASE ROUNDED = WS-STEP * WS-FACTOR
           MOVE WS-BASE TO OUT-BASE-PREM WS-PREM.

       3100-EXPERIENCE-MOD.
           EVALUATE TRUE
               WHEN POL-CLAIMS-3YR >= 3
                   MOVE 1.25 TO WS-EXP-MOD
               WHEN POL-CLAIMS-3YR = 0 AND POL-YRS-IN-BUS >= 3
                   MOVE 0.90 TO WS-EXP-MOD
               WHEN OTHER
                   MOVE 1.00 TO WS-EXP-MOD
           END-EVALUATE
           COMPUTE WS-PREM ROUNDED = WS-PREM * WS-EXP-MOD.

      * Deductible credits apply to property and auto only.
       3200-DEDUCTIBLE-CREDIT.
           MOVE 1.00 TO WS-DED-FACTOR
           IF POL-LINE = 'PR' OR POL-LINE = 'CA'
               EVALUATE TRUE
                   WHEN POL-DEDUCT >= 5000
                       MOVE 0.92 TO WS-DED-FACTOR
                   WHEN POL-DEDUCT >= 2500
                       MOVE 0.95 TO WS-DED-FACTOR
                   WHEN POL-DEDUCT >= 1000
                       MOVE 0.98 TO WS-DED-FACTOR
               END-EVALUATE
           END-IF
           COMPUTE WS-PREM ROUNDED = WS-PREM * WS-DED-FACTOR.

       3300-SCHEDULE-MOD.
           MOVE POL-SCHED-MOD TO WS-SCHED
           IF WS-SCHED < -0.25
               MOVE -0.25 TO WS-SCHED
           END-IF
           IF WS-SCHED > 0.25
               MOVE 0.25 TO WS-SCHED
           END-IF
           COMPUTE WS-PREM ROUNDED = WS-PREM * (1 + WS-SCHED).

       3400-MULTI-POLICY.
           IF POL-MULTI-POL = 'Y'
              AND (POL-LINE = 'GL' OR POL-LINE = 'PR')
               COMPUTE WS-PREM ROUNDED = WS-PREM * 0.95
           END-IF.

      * Wind surcharge per underwriting bulletin 14. The factor is
      * carried on the territory table under territory WND.
       3450-WIND-SURCHARGE.
           MOVE 1.000 TO WS-WIND-FACTOR
           IF POL-LINE = 'PR' AND POL-STATE = 'FL'
               PERFORM VARYING WS-I FROM 1 BY 1 UNTIL WS-I > TT-COUNT
                   IF TT-LINE (WS-I) = 'PR'
                      AND TT-TERR (WS-I) = 'WND'
                       MOVE TT-FACTOR (WS-I) TO WS-WIND-FACTOR
                   END-IF
               END-PERFORM
               COMPUTE WS-PREM ROUNDED = WS-PREM * WS-WIND-FACTOR
           END-IF.

      * Batch applies the minimum after every credit and debit.
       3500-MINIMUM-PREMIUM.
           MOVE 'N' TO WS-FOUND
           MOVE ZERO TO WS-MINIMUM
           PERFORM VARYING WS-I FROM 1 BY 1
                   UNTIL WS-I > MT-COUNT OR WS-FOUND = 'Y'
               IF MT-LINE (WS-I) = POL-LINE
                  AND MT-STATE (WS-I) = POL-STATE
                   MOVE 'Y' TO WS-FOUND
                   MOVE MT-MINIMUM (WS-I) TO WS-MINIMUM
               END-IF
           END-PERFORM
           PERFORM VARYING WS-I FROM 1 BY 1
                   UNTIL WS-I > MT-COUNT OR WS-FOUND = 'Y'
               IF MT-LINE (WS-I) = POL-LINE
                  AND MT-STATE (WS-I) = '**'
                   MOVE 'Y' TO WS-FOUND
                   MOVE MT-MINIMUM (WS-I) TO WS-MINIMUM
               END-IF
           END-PERFORM
           IF WS-FOUND = 'Y' AND WS-PREM < WS-MINIMUM
               MOVE WS-MINIMUM TO WS-PREM
               MOVE 'Y' TO OUT-MIN-FLAG
           END-IF
           MOVE WS-PREM TO OUT-MOD-PREM.

       3600-POLICY-FEE.
           MOVE WS-POLICY-FEE TO OUT-FEE
           COMPUTE OUT-TOTAL = WS-PREM + WS-POLICY-FEE.
