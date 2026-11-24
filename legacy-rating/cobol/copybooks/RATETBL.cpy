      * RATETBL - rating tables loaded from the flat files at start
       01  WS-CLASS-TBL.
           05  CT-COUNT            PIC 9(3) VALUE 0.
           05  CT-ROW OCCURS 60 TIMES.
               10  CT-LINE         PIC X(2).
               10  CT-CLASS        PIC X(5).
               10  CT-RATE         PIC 9(5)V9(4).
               10  CT-FROM         PIC 9(8).
               10  CT-TO           PIC 9(8).
       01  WS-TERR-TBL.
           05  TT-COUNT            PIC 9(3) VALUE 0.
           05  TT-ROW OCCURS 60 TIMES.
               10  TT-LINE         PIC X(2).
               10  TT-TERR         PIC X(3).
               10  TT-FACTOR       PIC 9V999.
               10  TT-FROM         PIC 9(8).
               10  TT-TO           PIC 9(8).
       01  WS-ELIG-TBL.
           05  ET-COUNT            PIC 9(3) VALUE 0.
           05  ET-ROW OCCURS 60 TIMES.
               10  ET-LINE         PIC X(2).
               10  ET-CLASS        PIC X(5).
               10  ET-STATE        PIC X(2).
               10  ET-ELIG         PIC X.
               10  ET-REASON       PIC X(4).
       01  WS-MIN-TBL.
           05  MT-COUNT            PIC 9(3) VALUE 0.
           05  MT-ROW OCCURS 60 TIMES.
               10  MT-LINE         PIC X(2).
               10  MT-STATE        PIC X(2).
               10  MT-MINIMUM      PIC 9(7)V99.
       01  WS-OVR-TBL.
           05  OT-COUNT            PIC 9(3) VALUE 0.
           05  OT-ROW OCCURS 60 TIMES.
               10  OT-LINE         PIC X(2).
               10  OT-CLASS        PIC X(5).
               10  OT-TERR         PIC X(3).
               10  OT-FACTOR       PIC 9V999.
               10  OT-FROM         PIC 9(8).
               10  OT-TO           PIC 9(8).
