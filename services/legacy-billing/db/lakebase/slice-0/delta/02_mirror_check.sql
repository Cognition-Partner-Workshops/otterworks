-- Mirror gate: every slice-0 reference table on Delta holds exactly the snapshot's rows.
SELECT 'codes' AS t,
       (SELECT COUNT(*) FROM ow_tp.mig_unt19_20261030_src.codes) AS src_rows,
       (SELECT COUNT(*) FROM ow_tp.mig_unt19_20261030_slice_0.codes) AS mirror_rows,
       (SELECT COUNT(*) FROM (SELECT * FROM ow_tp.mig_unt19_20261030_src.codes
                              EXCEPT ALL SELECT * FROM ow_tp.mig_unt19_20261030_slice_0.codes)) AS src_minus_mirror,
       (SELECT COUNT(*) FROM (SELECT * FROM ow_tp.mig_unt19_20261030_slice_0.codes
                              EXCEPT ALL SELECT * FROM ow_tp.mig_unt19_20261030_src.codes)) AS mirror_minus_src
UNION ALL
SELECT 'plans',
       (SELECT COUNT(*) FROM ow_tp.mig_unt19_20261030_src.plans),
       (SELECT COUNT(*) FROM ow_tp.mig_unt19_20261030_slice_0.plans),
       (SELECT COUNT(*) FROM (SELECT * FROM ow_tp.mig_unt19_20261030_src.plans
                              EXCEPT ALL SELECT * FROM ow_tp.mig_unt19_20261030_slice_0.plans)),
       (SELECT COUNT(*) FROM (SELECT * FROM ow_tp.mig_unt19_20261030_slice_0.plans
                              EXCEPT ALL SELECT * FROM ow_tp.mig_unt19_20261030_src.plans))
UNION ALL
SELECT 'tenants',
       (SELECT COUNT(*) FROM ow_tp.mig_unt19_20261030_src.tenants),
       (SELECT COUNT(*) FROM ow_tp.mig_unt19_20261030_slice_0.tenants),
       (SELECT COUNT(*) FROM (SELECT * FROM ow_tp.mig_unt19_20261030_src.tenants
                              EXCEPT ALL SELECT * FROM ow_tp.mig_unt19_20261030_slice_0.tenants)),
       (SELECT COUNT(*) FROM (SELECT * FROM ow_tp.mig_unt19_20261030_slice_0.tenants
                              EXCEPT ALL SELECT * FROM ow_tp.mig_unt19_20261030_src.tenants))
