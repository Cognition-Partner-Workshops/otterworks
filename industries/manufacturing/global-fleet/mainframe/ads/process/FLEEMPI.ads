*-----------------------------------------------------------------------
ADD PROCESS FLEEMPI-PREMAP VERSION 1
    MODULE SOURCE FOLLOWS
    MOVE SPACES TO WK-MSG.
    IF WK-EMPID EQ SPACES
        DO.
        DISPLAY.
        END.
    MOVE WK-EMPID TO EM-EMPID.
    OBTAIN CALC EMPLOYEE.
    IF DB-REC-NOT-FOUND
        DO.
        MOVE 'EMPLOYEE NOT ON FILE' TO WK-MSG.
        DISPLAY.
        END.
    WHILE EM-STAT EQ 'T'
        REPEAT.
        OBTAIN DUPLICATE EMPLOYEE.
        IF DB-REC-NOT-FOUND
            DO.
            MOVE 'EMPLOYEE HAS LEFT' TO WK-MSG.
            DISPLAY.
            END.
        END.
    OBTAIN FIRST ASSIGNMENT WITHIN EMP-ASSIGN.
    IF DB-END-OF-SET
        DO.
        MOVE 'NO COMPANY CAR HELD' TO WK-MSG.
        DISPLAY.
        END.
    OBTAIN OWNER WITHIN VEH-ASSIGN.
    MOVE CURRENT DATE TO WK-TODAY.
    CALL MONDAYS.
    COMPUTE WK-BENEFIT ROUNDED =
        VH-LIST * VH-BPCT / 1200 - EM-CNTRB.
    IF WK-BENEFIT LT 0
        MOVE 0 TO WK-BENEFIT.
    DISPLAY.
    MSEND.
*-----------------------------------------------------------------------
    DEFINE SUBROUTINE MONDAYS.
    MOVE WK-TODAY(1:6) TO WK-PERIOD.
    MOVE WK-PERIOD TO BP-PERIOD.
    OBTAIN CALC BENEFIT-PERIOD.
    IF DB-STATUS-OK
        COMPUTE WK-MDAYS =
            DATEDIF(BP-STRT, BP-END) + 1.
    GOBACK.
*-----------------------------------------------------------------------
ADD PROCESS FLEEMPI-ENTER VERSION 1
    MODULE SOURCE FOLLOWS
    IF WK-EMPID EQ SPACES
        DO.
        MOVE 'ENTER AN EMPLOYEE ID' TO WK-MSG.
        DISPLAY.
        END.
    EXECUTE NEXT FUNCTION.
    MSEND.
*-----------------------------------------------------------------------
ADD PROCESS FLEEMPI-PF3 VERSION 1
    MODULE SOURCE FOLLOWS
    MOVE SPACES TO WK-EMPID.
    TRANSFER CONTROL TO 'FLEMENU' NOFINISH.
    MSEND.
