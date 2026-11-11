/* run=dbx-d1111 act=scale step=${STEP} consumer=m_SFX_STG_CUSTOMER_ACCOUNT */
INSERT OVERWRITE cpw.dbx_d1111_after.billing__sfx_stg_customer_account
SELECT CAST(CAST(customer_id AS STRING) AS BIGINT),
 CAST(CAST(owner_user_id AS STRING) AS BIGINT),
 ltrim(rtrim(CAST(account_name AS STRING))),
 upper(ltrim(rtrim(CAST(status_cd AS STRING)))),
 coalesce(upper(ltrim(rtrim(CAST(currency_cd AS STRING)))), '${CURRENCY_DEFAULT}'),
 to_date(CAST(created_dt AS STRING), 'yyyy-MM-dd'),
 upper(ltrim(rtrim(CAST(account_number AS STRING))))
FROM cpw.dbx_d1111_before.billing__stg_customer_account;
