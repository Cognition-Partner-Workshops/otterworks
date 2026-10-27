      *----------------------------------------------------------------*
      * FLVEHU   VEHICLE UNLOAD RECORD                  LRECL 100 FB   *
      *----------------------------------------------------------------*
       01  FLVEHU-REC.
           05  VU-DBKEY              PIC 9(10).
           05  VU-VEHID              PIC X(8).
           05  VU-PLATE              PIC X(8).
           05  VU-MAKE               PIC X(12).
           05  VU-MODL               PIC X(16).
           05  VU-LIST               PIC S9(7)V99 COMP-3.
           05  VU-CO2                PIC 9(3).
           05  VU-BPCT               PIC 9(2)V99.
           05  VU-FUEL               PIC X(1).
           05  VU-REGD               PIC 9(8).
           05  VU-OWNR-EMPID         PIC X(8).
           05  VU-OWNR-DBKEY         PIC 9(10).
           05  FILLER                PIC X(7).
