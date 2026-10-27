*-----------------------------------------------------------------------
*  IDMSDDDL  SCHEMA COMPILE
*  DICTNAME FLTDICT   PUNCHED 2019-02-14  LAST CHANGE 2023-06-02
*-----------------------------------------------------------------------
ADD SCHEMA NAME IS FLEETSCH VERSION IS 1
    SCHEMA DESCRIPTION IS 'COMPANY CAR FLEET'
    MEMO DATE IS 02/14/19
    ASSIGN RECORD IDS FROM 1001
    PUBLIC ACCESS IS ALLOWED FOR ALL
    .
ADD AREA NAME IS EMP-REGION
    .
ADD AREA NAME IS FLEET-REGION
    .
ADD AREA NAME IS CLAIM-REGION
    .
*-----------------------------------------------------------------------
ADD RECORD NAME IS EMPLOYEE
    RECORD ID IS 1001
    LOCATION MODE IS CALC USING ( EM-EMPID )
        DUPLICATES ARE LAST
    WITHIN AREA EMP-REGION
    .
    03 EM-EMPID              PIC X(8).
    03 EM-SURN               PIC X(20).
    03 EM-FORN               PIC X(15).
    03 EM-GRD                PIC 9(2).
    03 EM-CC                 PIC X(6).
    03 EM-HIRE               PIC 9(8).
    03 EM-LEAV               PIC 9(8).
    03 EM-STAT               PIC X(1).
       88 EM-ACTIVE          VALUE 'A'.
       88 EM-TERMINATED      VALUE 'T'.
       88 EM-TRANSFERRED     VALUE 'X'.
    03 EM-CNTRB              PIC S9(5)V99 COMP-3.
    03 EM-LOC                PIC X(4).
    03 FILLER                PIC X(10).
*-----------------------------------------------------------------------
ADD RECORD NAME IS VEHICLE
    RECORD ID IS 1002
    LOCATION MODE IS CALC USING ( VH-VEHID )
        DUPLICATES ARE NOT ALLOWED
    WITHIN AREA FLEET-REGION
    .
    03 VH-VEHID              PIC X(8).
    03 VH-PLATE              PIC X(8).
    03 VH-MAKE               PIC X(12).
    03 VH-MODL               PIC X(16).
    03 VH-LIST               PIC S9(7)V99 COMP-3.
    03 VH-CO2                PIC 9(3).
    03 VH-BPCT               PIC 9(2)V99.
    03 VH-FUEL               PIC X(1).
       88 VH-PETROL          VALUE 'P'.
       88 VH-DIESEL          VALUE 'D'.
       88 VH-HYBRID          VALUE 'H'.
       88 VH-ELECTRIC        VALUE 'E'.
    03 VH-REGD               PIC 9(8).
    03 FILLER                PIC X(8).
*-----------------------------------------------------------------------
ADD RECORD NAME IS ASSIGNMENT
    RECORD ID IS 1003
    LOCATION MODE IS VIA EMP-ASSIGN SET
    WITHIN AREA FLEET-REGION
    .
    03 AS-ASGID              PIC X(10).
    03 AS-STRT               PIC 9(8).
    03 AS-END                PIC 9(8).
    03 AS-RSN                PIC X(2).
       88 AS-NEW-CAR         VALUE 'NC'.
       88 AS-REPLACEMENT     VALUE 'RP'.
       88 AS-POOL-LOAN       VALUE 'PL'.
    03 FILLER                PIC X(4).
*-----------------------------------------------------------------------
ADD RECORD NAME IS MILEAGE-CLAIM
    RECORD ID IS 1004
    LOCATION MODE IS VIA EMP-CLAIM SET
    WITHIN AREA CLAIM-REGION
    .
    03 MC-CLMID              PIC X(10).
    03 MC-VEHID              PIC X(8).
    03 MC-DATE               PIC 9(8).
    03 MC-MILES              PIC 9(5).
    03 MC-STAT               PIC X(1).
       88 MC-APPROVED        VALUE 'A'.
       88 MC-PENDING         VALUE 'P'.
       88 MC-REJECTED        VALUE 'R'.
    03 MC-PURP               PIC X(10).
*-----------------------------------------------------------------------
ADD RECORD NAME IS BENEFIT-PERIOD
    RECORD ID IS 1005
    LOCATION MODE IS CALC USING ( BP-PERIOD )
        DUPLICATES ARE NOT ALLOWED
    WITHIN AREA CLAIM-REGION
    .
    03 BP-PERIOD             PIC 9(6).
    03 BP-STRT               PIC 9(8).
    03 BP-END                PIC 9(8).
    03 BP-MRATE              PIC 9V999.
    03 BP-STAT               PIC X(1).
       88 BP-OPEN            VALUE 'O'.
       88 BP-CLOSED          VALUE 'C'.
    03 BP-RUNDT              PIC 9(8).
*-----------------------------------------------------------------------
ADD SET NAME IS EMP-ASSIGN
    ORDER IS SORTED
    MODE IS CHAIN LINKED TO PRIOR
    OWNER IS EMPLOYEE
        NEXT DBKEY POSITION IS 1
        PRIOR DBKEY POSITION IS 2
    MEMBER IS ASSIGNMENT
        NEXT DBKEY POSITION IS 1
        PRIOR DBKEY POSITION IS 2
        LINKED TO OWNER
        OWNER DBKEY POSITION IS 3
        MANDATORY AUTOMATIC
        KEY IS ( AS-STRT DESCENDING )
        DUPLICATES ARE LAST
    .
ADD SET NAME IS VEH-ASSIGN
    ORDER IS LAST
    MODE IS CHAIN LINKED TO PRIOR
    OWNER IS VEHICLE
        NEXT DBKEY POSITION IS 1
        PRIOR DBKEY POSITION IS 2
    MEMBER IS ASSIGNMENT
        NEXT DBKEY POSITION IS 4
        PRIOR DBKEY POSITION IS 5
        LINKED TO OWNER
        OWNER DBKEY POSITION IS 6
        MANDATORY AUTOMATIC
    .
ADD SET NAME IS EMP-VEHICLE
    ORDER IS NEXT
    MODE IS CHAIN LINKED TO PRIOR
    OWNER IS EMPLOYEE
        NEXT DBKEY POSITION IS 3
        PRIOR DBKEY POSITION IS 4
    MEMBER IS VEHICLE
        NEXT DBKEY POSITION IS 3
        PRIOR DBKEY POSITION IS 4
        LINKED TO OWNER
        OWNER DBKEY POSITION IS 5
        OPTIONAL MANUAL
    .
ADD SET NAME IS EMP-CLAIM
    ORDER IS SORTED
    MODE IS CHAIN LINKED TO PRIOR
    OWNER IS EMPLOYEE
        NEXT DBKEY POSITION IS 5
        PRIOR DBKEY POSITION IS 6
    MEMBER IS MILEAGE-CLAIM
        NEXT DBKEY POSITION IS 1
        PRIOR DBKEY POSITION IS 2
        LINKED TO OWNER
        OWNER DBKEY POSITION IS 3
        MANDATORY AUTOMATIC
        KEY IS ( MC-DATE ASCENDING )
        DUPLICATES ARE LAST
    .
ADD SET NAME IS PERIOD-CLAIM
    ORDER IS LAST
    MODE IS CHAIN LINKED TO PRIOR
    OWNER IS BENEFIT-PERIOD
        NEXT DBKEY POSITION IS 1
        PRIOR DBKEY POSITION IS 2
    MEMBER IS MILEAGE-CLAIM
        NEXT DBKEY POSITION IS 4
        PRIOR DBKEY POSITION IS 5
        OPTIONAL AUTOMATIC
    .
VALIDATE.
GENERATE.
