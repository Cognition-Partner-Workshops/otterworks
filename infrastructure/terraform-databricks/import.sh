#!/usr/bin/env bash
set -u

terraform import 'databricks_catalog.ow_tp' 'ow_tp' || true
terraform import 'databricks_schema.ow_tp_bronze' 'ow_tp.bronze' || true
terraform import 'databricks_schema.ow_tp_silver' 'ow_tp.silver' || true
terraform import 'databricks_schema.ow_tp_gold' 'ow_tp.gold' || true
terraform import 'databricks_volume.ow_tp_bronze_landing' 'ow_tp.bronze.landing' || true
terraform import 'databricks_secret_scope.ow_tp' 'ow_tp' || true
