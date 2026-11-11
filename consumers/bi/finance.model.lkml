connection: "tdprod_fin"
include: "/views/*.view.lkml"

datagroup: finance_four_hours {
  interval_trigger: "4 hours"
  max_cache_age: "4 hours"
}
persist_with: finance_four_hours

access_grant: finance_enabled {
  user_attribute: finance_warehouse_enabled
  allowed_values: ["yes"]
}

explore: invoices {
  required_access_grants: [finance_enabled]
  join: accounts {
    type: left_outer
    sql_on: ${invoices.account_id} = ${accounts.account_id} ;;
    relationship: many_to_one
  }
  join: customers {
    type: left_outer
    sql_on: ${accounts.customer_id} = ${customers.customer_id} ;;
    relationship: many_to_one
  }
}
explore: payments {
  required_access_grants: [finance_enabled]
}
explore: gl_journal {
  required_access_grants: [finance_enabled]
  join: gl_accounts {
    type: left_outer
    sql_on: ${gl_journal.gl_account_cd} = ${gl_accounts.gl_account_cd} ;;
    relationship: many_to_one
  }
}
explore: overdue_accounts {
  required_access_grants: [finance_enabled]
}

explore: invoice_revenue {
  required_access_grants: [finance_enabled]
}
