lines = open("dpi_ls/governance_resource_evaluation_service.py", encoding="utf-8").readlines()
lines = [l for l in lines if "(True, True, False, True)" not in l]
open("dpi_ls/governance_resource_evaluation_service.py", "w", encoding="utf-8").writelines(lines)
