# COMMISSION_DW parallel-run contract
The paused job compares the production legacy baseline with the two migrated outputs.
Each cycle runs fact_commission first, then the dependent agent commission summary.
A green cycle requires both recon reports to be PASS with all checks and reruns passing.
Any failed task or report is a red cycle and stops the dependent summary task.
The `staged_red` switch turns a passing verification run into an intentional red trigger.
Staged-red failure text identifies the verification drill and preserves the PASS report.
Reports land under `/Volumes/ow_tp/bronze/landing/<ns>/recon/<run_id>/<unit>/`.
The report path is printed by the trigger command for each completed notebook task.
The schedule is UTC `0 0 6 * * ?`, remains PAUSED until approval, and runs serially.
Each cycle costs approximately two full reloads plus two recon reads.
Expected serverless cost is approximately 2–3 warehouse-minutes per cycle.
The parent opens the window only after approval and the staged-red drill.
STOP E entry requires three consecutive green scheduled cycles.
No cutover or consumer change is performed by this job.
