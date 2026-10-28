SELECT to_json(struct(*)) AS row_json
FROM ow_tp.ow_tp_dunning_risk.ow_tp_scores
ORDER BY tenant_id, subscription_id;
