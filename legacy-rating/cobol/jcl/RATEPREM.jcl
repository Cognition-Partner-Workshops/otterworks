//RATEPREM JOB (RATE),'NIGHTLY RATING',CLASS=A,MSGCLASS=X,
//         NOTIFY=&SYSUID,REGION=0M
//*-------------------------------------------------------------------*
//* RATEPREM - nightly premium rating batch                           *
//*                                                                   *
//* Documentation only: on the demo platform this job is performed by *
//* run.sh (GnuCOBOL RATEPREM against legacy-rating/tables). This     *
//* member shows the equivalent z/OS batch: sort the day's policies   *
//* by policy id, rate them against the five flat-file tables, and    *
//* write the rated file plus a control total. POLREC and RATEOUT are *
//* both RECFM=FB LRECL=80. Symbolics are filled by the scheduler.    *
//*-------------------------------------------------------------------*
//         SET RUNDATE=D20261124
//         SET HLQ=RATE.PROD
//*
//*---- STEP010: SORT - policies into policy-id order ----------------*
//STEP010  EXEC PGM=SORT
//SYSOUT   DD SYSOUT=*
//SORTIN   DD DISP=SHR,DSN=&HLQ..POLICIES.&RUNDATE
//SORTOUT  DD DSN=&&POLSRT,DISP=(NEW,PASS),
//            SPACE=(CYL,(5,1),RLSE),
//            DCB=(RECFM=FB,LRECL=80,BLKSIZE=0)
//SYSIN    DD *
  SORT FIELDS=(1,8,CH,A)
/*
//*
//*---- STEP020: RATEPREM - rate every policy ------------------------*
//STEP020  EXEC PGM=RATEPREM,COND=(0,NE,STEP010)
//STEPLIB  DD DISP=SHR,DSN=&HLQ..LOADLIB
//POLICIES DD DSN=&&POLSRT,DISP=(OLD,DELETE)
//CLASSTBL DD DISP=SHR,DSN=&HLQ..TABLES(CLASSFAC)
//TERRTBL  DD DISP=SHR,DSN=&HLQ..TABLES(TERRFAC)
//ELIGTBL  DD DISP=SHR,DSN=&HLQ..TABLES(LINEELIG)
//MINPTBL  DD DISP=SHR,DSN=&HLQ..TABLES(MINPREM)
//OVRDTBL  DD DISP=SHR,DSN=&HLQ..TABLES(OVERRIDE)
//RATED    DD DSN=&HLQ..RATED.&RUNDATE,DISP=(NEW,CATLG,DELETE),
//            SPACE=(CYL,(5,1),RLSE),
//            DCB=(RECFM=FB,LRECL=80,BLKSIZE=0)
//SYSOUT   DD SYSOUT=*
//*
//*---- STEP030: IDCAMS - keep the control total with the output -----*
//STEP030  EXEC PGM=IDCAMS,COND=(4,LT,STEP020)
//SYSPRINT DD SYSOUT=*
//SYSIN    DD *
  PRINT INFILE(RATED) COUNT(1)
/*
//RATED    DD DISP=SHR,DSN=&HLQ..RATED.&RUNDATE
