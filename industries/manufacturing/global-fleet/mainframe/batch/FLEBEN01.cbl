       IDENTIFICATION DIVISION.
       PROGRAM-ID.    FLEBEN01.
       AUTHOR.        FLEET SYSTEMS.
       DATE-WRITTEN.  1998-03-09.
      *----------------------------------------------------------------*
      * MONTHLY COMPANY CAR BENEFIT RUN                                *
      * READS THE FLEET DATABASE FOR ONE CLOSED BENEFIT PERIOD AND     *
      * WRITES ONE BENOUT RECORD PER EMPLOYEE WITH A CAR OR APPROVED   *
      * BUSINESS MILEAGE IN THE PERIOD, PLUS THE CONTROL REPORT.       *
      *                                                                *
      * PARM CARD (SYSIN)  COL 1-6  PERIOD YYYYMM                      *
      *----------------------------------------------------------------*
      * 1998-03-09  INITIAL VERSION                                    *
      * 2003-11-17  MILEAGE REIMBURSEMENT ADDED TO BENOUT              *
      * 2011-04-04  EMPLOYEE CONTRIBUTION DEDUCTED                     *
      * 2016-08-22  LEAVERS CAPPED AT LEAVING DATE, FLAG L             *
      * 2019-02-14  MOVED TO FLEETSCH VERSION 1 / FLEETSS2             *
      *----------------------------------------------------------------*
       ENVIRONMENT DIVISION.
       CONFIGURATION SECTION.
       SOURCE-COMPUTER. IBM-ZOS.
       OBJECT-COMPUTER. IBM-ZOS.
       IDMS-CONTROL SECTION.
       PROTOCOL.      MODE IS BATCH DEBUG
                      IDMS-RECORDS MANUAL.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT PARM-FILE   ASSIGN TO SYSIN.
           SELECT BENOUT-FILE ASSIGN TO BENOUT
                  FILE STATUS IS WS-BENOUT-FS.
           SELECT REPORT-FILE ASSIGN TO BENRPT.
       DATA DIVISION.
       SCHEMA SECTION.
       DB FLEETSS2 WITHIN FLEETSCH VERSION 1.
       FILE SECTION.
       FD  PARM-FILE
           RECORDING MODE IS F.
       01  PARM-REC.
           05  PARM-PERIOD           PIC 9(6).
           05  FILLER                PIC X(74).
       FD  BENOUT-FILE
           RECORDING MODE IS F
           BLOCK CONTAINS 0 RECORDS.
           COPY FLBOUT.
       FD  REPORT-FILE
           RECORDING MODE IS F.
       01  REPORT-LINE               PIC X(133).
       WORKING-STORAGE SECTION.
       01  COPY IDMS SUBSCHEMA-CONTROL.
       01  COPY IDMS EMPLOYEE.
       01  COPY IDMS VEHICLE.
       01  COPY IDMS ASSIGNMENT.
       01  COPY IDMS MILEAGE-CLAIM.
       01  COPY IDMS BENEFIT-PERIOD.
       01  WS-SWITCHES.
           05  WS-EMP-EOF            PIC X     VALUE 'N'.
               88  NO-MORE-EMPLOYEES           VALUE 'Y'.
           05  WS-SET-EOF            PIC X     VALUE 'N'.
               88  END-OF-MEMBERS              VALUE 'Y'.
           05  WS-HAVE-CAR           PIC X     VALUE 'N'.
               88  CAR-IN-PERIOD               VALUE 'Y'.
       01  WS-BENOUT-FS              PIC XX.
       01  WS-DATES.
           05  WS-PSTRT-INT          PIC S9(9) COMP.
           05  WS-PEND-INT           PIC S9(9) COMP.
           05  WS-FROM-INT           PIC S9(9) COMP.
           05  WS-TO-INT             PIC S9(9) COMP.
           05  WS-TO-DATE            PIC 9(8).
           05  WS-MDAYS              PIC 9(2).
       01  WS-WORK.
           05  WS-DAYS               PIC 9(2).
           05  WS-CLM-AMT            PIC S9(7)V99 COMP-3.
           05  WS-TAXB               PIC S9(7)V99 COMP-3.
       01  WS-TOTALS.
           05  WS-REC-COUNT          PIC 9(6)  COMP-3 VALUE 0.
           05  WS-TOT-TAXB           PIC S9(11)V99 COMP-3 VALUE 0.
           05  WS-TOT-MREIM          PIC S9(11)V99 COMP-3 VALUE 0.
       01  RPT-HEAD1.
           05  FILLER                PIC X(59) VALUE
               '1FLEBEN01  MONTHLY COMPANY CAR BENEFIT RUN'.
           05  FILLER                PIC X(7)  VALUE 'PERIOD '.
           05  RH1-YYYY              PIC 9(4).
           05  FILLER                PIC X     VALUE '-'.
           05  RH1-MM                PIC 99.
       01  RPT-HEAD2                 PIC X(80) VALUE
           ' EMP-ID   DBKEY      VEH-ID   DAYS   TAXABLE-BEN  MILES     MILE-REIM  F'.
       01  RPT-HEAD3                 PIC X(80) VALUE
           ' -------- ---------- -------- ---- ------------- ------ ------------- -'.
       01  RPT-DETAIL.
           05  FILLER                PIC X     VALUE SPACE.
           05  RD-EMPID              PIC X(8).
           05  FILLER                PIC X     VALUE SPACE.
           05  RD-DBKEY              PIC 9(10).
           05  FILLER                PIC X     VALUE SPACE.
           05  RD-VEHID              PIC X(8).
           05  FILLER                PIC X     VALUE SPACE.
           05  RD-DAYS               PIC ZZZ9.
           05  FILLER                PIC X     VALUE SPACE.
           05  RD-TAXB               PIC Z,ZZZ,ZZ9.99.
           05  FILLER                PIC X     VALUE SPACE.
           05  RD-MILES              PIC ZZZZZ9.
           05  FILLER                PIC X     VALUE SPACE.
           05  RD-MREIM              PIC Z,ZZZ,ZZ9.99.
           05  FILLER                PIC X     VALUE SPACE.
           05  RD-FLAG               PIC X.
       01  RPT-TOTAL.
           05  FILLER                PIC X(17) VALUE ' RECORDS WRITTEN '.
           05  RT-COUNT              PIC ZZZZZ9.
           05  FILLER                PIC X(17) VALUE '   TOTAL TAXABLE '.
           05  RT-TAXB               PIC ZZZ,ZZZ,ZZ9.99.
           05  FILLER                PIC X(20) VALUE
               '   TOTAL REIMBURSED '.
           05  RT-MREIM              PIC Z,ZZZ,ZZ9.99.
       PROCEDURE DIVISION.
       0000-MAIN.
           PERFORM 1000-INITIALISE
           PERFORM 2000-EMPLOYEE UNTIL NO-MORE-EMPLOYEES
           PERFORM 9000-FINISH
           GOBACK.
      *
       1000-INITIALISE.
           OPEN INPUT  PARM-FILE
                OUTPUT BENOUT-FILE REPORT-FILE
           READ PARM-FILE
           BIND RUN-UNIT
           PERFORM IDMS-STATUS
           BIND EMPLOYEE
           BIND VEHICLE
           BIND ASSIGNMENT
           BIND MILEAGE-CLAIM
           BIND BENEFIT-PERIOD
           READY EMP-REGION   USAGE-MODE IS RETRIEVAL
           READY FLEET-REGION USAGE-MODE IS RETRIEVAL
           READY CLAIM-REGION USAGE-MODE IS RETRIEVAL
           PERFORM IDMS-STATUS
           MOVE PARM-PERIOD TO BP-PERIOD
           OBTAIN CALC BENEFIT-PERIOD
           PERFORM IDMS-STATUS
           COMPUTE WS-PSTRT-INT = FUNCTION INTEGER-OF-DATE(BP-STRT)
           COMPUTE WS-PEND-INT  = FUNCTION INTEGER-OF-DATE(BP-END)
           COMPUTE WS-MDAYS     = WS-PEND-INT - WS-PSTRT-INT + 1
           MOVE BP-PERIOD(1:4) TO RH1-YYYY
           MOVE BP-PERIOD(5:2) TO RH1-MM
           WRITE REPORT-LINE FROM RPT-HEAD1
           WRITE REPORT-LINE FROM RPT-HEAD2
           WRITE REPORT-LINE FROM RPT-HEAD3
           OBTAIN FIRST EMPLOYEE WITHIN EMP-REGION
           IF ERROR-STATUS = '0307'
               SET NO-MORE-EMPLOYEES TO TRUE
           ELSE
               PERFORM IDMS-STATUS
           END-IF.
      *
       2000-EMPLOYEE.
           IF EM-HIRE > BP-END
              OR (EM-LEAV NOT = 0 AND EM-LEAV < BP-STRT)
               CONTINUE
           ELSE
               PERFORM 2100-BENEFIT
               PERFORM 2200-MILEAGE
               IF WS-DAYS > 0 OR BO-MILES > 0
                   PERFORM 2300-WRITE
               END-IF
           END-IF
           OBTAIN NEXT EMPLOYEE WITHIN EMP-REGION
           IF ERROR-STATUS = '0307'
               SET NO-MORE-EMPLOYEES TO TRUE
           ELSE
               PERFORM IDMS-STATUS
           END-IF.
      *
       2100-BENEFIT.
           INITIALIZE FLBOUT-REC
           MOVE 0   TO WS-DAYS
           MOVE 'N' TO WS-SET-EOF WS-HAVE-CAR
           OBTAIN FIRST ASSIGNMENT WITHIN EMP-ASSIGN
           PERFORM UNTIL END-OF-MEMBERS OR CAR-IN-PERIOD
               IF ERROR-STATUS = '0307'
                   SET END-OF-MEMBERS TO TRUE
               ELSE
                   PERFORM IDMS-STATUS
                   IF AS-STRT NOT > BP-END
                       SET CAR-IN-PERIOD TO TRUE
                   ELSE
                       OBTAIN NEXT ASSIGNMENT WITHIN EMP-ASSIGN
                   END-IF
               END-IF
           END-PERFORM
           IF CAR-IN-PERIOD
              AND (AS-END = 0 OR AS-END NOT < BP-STRT)
               COMPUTE WS-FROM-INT =
                   FUNCTION MAX(FUNCTION INTEGER-OF-DATE(AS-STRT)
                                WS-PSTRT-INT)
               MOVE BP-END TO WS-TO-DATE
               IF AS-END NOT = 0 AND AS-END < WS-TO-DATE
                   MOVE AS-END TO WS-TO-DATE
               END-IF
               IF EM-LEAV NOT = 0 AND EM-LEAV < WS-TO-DATE
                   MOVE EM-LEAV TO WS-TO-DATE
               END-IF
               COMPUTE WS-TO-INT = FUNCTION INTEGER-OF-DATE(WS-TO-DATE)
               IF WS-TO-INT NOT < WS-FROM-INT
                   COMPUTE WS-DAYS = WS-TO-INT - WS-FROM-INT + 1
               END-IF
               OBTAIN OWNER WITHIN VEH-ASSIGN
               PERFORM IDMS-STATUS
               MOVE VH-VEHID TO BO-VEHID
               IF WS-DAYS > 0
                   COMPUTE WS-TAXB =
                       (VH-LIST * VH-BPCT / 1200 - EM-CNTRB)
                       * WS-DAYS / WS-MDAYS
                   IF WS-TAXB < 0
                       MOVE 0 TO WS-TAXB
                   END-IF
                   MOVE WS-TAXB TO BO-TAXB
               END-IF
           END-IF
           IF WS-DAYS = 0
               MOVE SPACES TO BO-VEHID
           END-IF.
      *
       2200-MILEAGE.
           MOVE 0   TO BO-MILES BO-MREIM
           MOVE 'N' TO WS-SET-EOF
           OBTAIN FIRST MILEAGE-CLAIM WITHIN EMP-CLAIM
           PERFORM UNTIL END-OF-MEMBERS
               IF ERROR-STATUS = '0307'
                   SET END-OF-MEMBERS TO TRUE
               ELSE
                   PERFORM IDMS-STATUS
                   IF MC-DATE > BP-END
                       SET END-OF-MEMBERS TO TRUE
                   ELSE
                       IF MC-DATE NOT < BP-STRT AND MC-APPROVED
                           COMPUTE WS-CLM-AMT ROUNDED =
                               MC-MILES * BP-MRATE
                           ADD MC-MILES   TO BO-MILES
                           ADD WS-CLM-AMT TO BO-MREIM
                       END-IF
                       OBTAIN NEXT MILEAGE-CLAIM WITHIN EMP-CLAIM
                   END-IF
               END-IF
           END-PERFORM.
      *
       2300-WRITE.
           MOVE BP-PERIOD TO BO-PERIOD
           MOVE EM-EMPID  TO BO-EMPID
           ACCEPT BO-EMP-DBKEY FROM IDMS-DBKEY FOR EMPLOYEE
           MOVE WS-DAYS   TO BO-DAYS
           IF EM-LEAV NOT < BP-STRT AND EM-LEAV NOT > BP-END
               MOVE 'L' TO BO-FLAG
           ELSE
               MOVE SPACE TO BO-FLAG
           END-IF
           WRITE FLBOUT-REC
           MOVE BO-EMPID     TO RD-EMPID
           MOVE BO-EMP-DBKEY TO RD-DBKEY
           MOVE BO-VEHID     TO RD-VEHID
           MOVE BO-DAYS      TO RD-DAYS
           MOVE BO-TAXB      TO RD-TAXB
           MOVE BO-MILES     TO RD-MILES
           MOVE BO-MREIM     TO RD-MREIM
           MOVE BO-FLAG      TO RD-FLAG
           WRITE REPORT-LINE FROM RPT-DETAIL
           ADD 1        TO WS-REC-COUNT
           ADD BO-TAXB  TO WS-TOT-TAXB
           ADD BO-MREIM TO WS-TOT-MREIM.
      *
       9000-FINISH.
           MOVE WS-REC-COUNT TO RT-COUNT
           MOVE WS-TOT-TAXB  TO RT-TAXB
           MOVE WS-TOT-MREIM TO RT-MREIM
           WRITE REPORT-LINE FROM RPT-TOTAL
           FINISH
           CLOSE PARM-FILE BENOUT-FILE REPORT-FILE.
      *
       COPY IDMS IDMS-STATUS.
       IDMS-ABORT SECTION.
           DISPLAY 'FLEBEN01 IDMS ERROR ' ERROR-STATUS
                   ' RECORD ' ERROR-RECORD ' SET ' ERROR-SET
           MOVE 16 TO RETURN-CODE
           ROLLBACK
           STOP RUN.
