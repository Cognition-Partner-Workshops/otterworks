
  
BEGIN 
dbms_scheduler.create_job('"NIGHTLY_DISPOSITION"',
job_type=>'PLSQL_BLOCK', job_action=>
'BEGIN ARCHIVE.RETENTION_PKG.SNAPSHOT_CLASS_TOTALS(TRUNC(SYSDATE)); END;'
, number_of_arguments=>0,
start_date=>TO_TIMESTAMP_TZ('30-SEP-2026 04.40.46.568415000 AM +00:00','DD-MON-RRRR HH.MI.SSXFF AM TZR','NLS_DATE_LANGUAGE=english'), repeat_interval=> 
'FREQ=DAILY; BYHOUR=2; BYMINUTE=0; BYSECOND=0'
, end_date=>NULL,
job_class=>'"DEFAULT_JOB_CLASS"', enabled=>FALSE, auto_drop=>FALSE,comments=>
'Legacy nightly class-totals snapshot (prod: enabled, 02:00 site time).'
);
dbms_scheduler.set_attribute('"NIGHTLY_DISPOSITION"','max_failures',3);
sys.dbms_scheduler.set_attribute('"NIGHTLY_DISPOSITION"','NLS_ENV','NLS_LANGUAGE=''AMERICAN'' NLS_TERRITORY=''AMERICA'' NLS_CURRENCY=''$'' NLS_ISO_CURRENCY=''AMERICA'' NLS_NUMERIC_CHARACTERS=''.,'' NLS_CALENDAR=''GREGORIAN'' NLS_DATE_FORMAT=''DD-MON-RR'' NLS_DATE_LANGUAGE=''AMERICAN'' NLS_SORT=''BINARY'' NLS_TIME_FORMAT=''HH.MI.SSXFF AM'' NLS_TIMESTAMP_FORMAT=''DD-MON-RR HH.MI.SSXFF AM'' NLS_TIME_TZ_FORMAT=''HH.MI.SSXFF AM TZR'' NLS_TIMESTAMP_TZ_FORMAT=''DD-MON-RR HH.MI.SSXFF AM TZR'' NLS_DUAL_CURRENCY=''$'' NLS_COMP=''BINARY'' NLS_LENGTH_SEMANTICS=''BYTE'' NLS_NCHAR_CONV_EXCP=''FALSE''');
dbms_scheduler.set_attribute('"NIGHTLY_DISPOSITION"','restart_on_recovery',TRUE);
dbms_scheduler.set_attribute('"NIGHTLY_DISPOSITION"','restart_on_failure',TRUE);
COMMIT; 
END; 
