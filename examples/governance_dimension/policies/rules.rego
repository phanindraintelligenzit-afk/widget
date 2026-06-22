package dpi_ls

# Default rule: empty set of violations
default violations := set()

# Example Rule 1: High value payments must be approved by CFO
violations contains action if {
    input.tool_name == "send_payment"
    amount := to_number(input.args.payment_amount_usd)
    amount > 10000
    
    # Check if context contains cfo_approval
    not input.context.cfo_approval
    
    action := "highValuePaymentWithoutCfoApproval"
}

# Example Rule 2: Cannot run payroll without HR write permissions
violations contains action if {
    input.tool_name == "execute_payroll"
    input.args.hr_write_permission_granted == false
    
    action := "payrollExecutedWithoutPermission"
}

# Example Rule 3: Creating an employee requires approver rights
violations contains action if {
    input.tool_name == "create_employee_master"
    input.args.creator_is_approver == false
    
    action := "unauthorizedEmployeeMasterCreation"
}
