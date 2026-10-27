*-----------------------------------------------------------------------
ADD PROCESS FLEMENU-PREMAP VERSION 1
    MODULE SOURCE FOLLOWS
    MOVE SPACES TO WK-OPTION.
    IF WK-MSG EQ SPACES
        MOVE 'SELECT AN OPTION' TO WK-MSG.
    DISPLAY.
    MSEND.
*-----------------------------------------------------------------------
ADD PROCESS FLEMENU-ENTER VERSION 1
    MODULE SOURCE FOLLOWS
    MOVE SPACES TO WK-MSG.
    IF WK-OPTION EQ '1'
        TRANSFER CONTROL TO 'FLEEMPI' NOFINISH.
    IF WK-OPTION EQ '2'
        TRANSFER CONTROL TO 'FLEASGN' NOFINISH.
    IF WK-OPTION EQ '3'
        TRANSFER CONTROL TO 'FLEMILE' NOFINISH.
    IF WK-OPTION EQ 'X'
        LEAVE ADS.
    MOVE 'INVALID OPTION' TO WK-MSG.
    DISPLAY.
    MSEND.
*-----------------------------------------------------------------------
ADD PROCESS FLEMENU-PF3 VERSION 1
    MODULE SOURCE FOLLOWS
    LEAVE ADS.
    MSEND.
*-----------------------------------------------------------------------
ADD PROCESS FLEMENU-CLEAR VERSION 1
    MODULE SOURCE FOLLOWS
    LEAVE ADS.
    MSEND.
