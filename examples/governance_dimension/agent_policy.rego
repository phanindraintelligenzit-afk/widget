package agent.governance

# By default, actions are allowed only if there are no violations.
default allow := false

allow {
    count(violations) == 0
}

violations[msg] {
    input.action == "execute_wire_transfer"
    input.args.amount_usd > 500
    not input.context.finance_approved
    msg := sprintf("Wire transfer of $%.2f requires finance_approved=true.", [input.args.amount_usd])
}

violations[msg] {
    input.action == "delete_customer_records"
    not input.context.has_change_ticket
    msg := "Deleting customer records requires has_change_ticket=true."
}

violations[msg] {
    input.context.is_weekend
    msg := "Executing state-modifying actions is not permitted on weekends."
}
