import sys
import re

def patch_scoring():
    with open('api/scoring.py', 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Patch Cost
    target_cost = "evals = s.scalars(select(CostResourceEvaluationRow)).all()"
    replacement_cost = 'evals = s.scalars(select(CostResourceEvaluationRow).where(CostResourceEvaluationRow.resource_name.in_(["OpenLIT", "OpenCost"])).order_by(CostResourceEvaluationRow.id.desc()).limit(100)).all()'
    content = content.replace(target_cost, replacement_cost)

    # 2. Patch Quality
    target_quality_eq = "eq_evals = s.scalars(select(EnterpriseQualityResourceEvaluationRow)).all()"
    replacement_quality_eq = "eq_evals = s.scalars(select(EnterpriseQualityResourceEvaluationRow).order_by(EnterpriseQualityResourceEvaluationRow.id.desc()).limit(100)).all()"
    content = content.replace(target_quality_eq, replacement_quality_eq)
    
    # 3. Patch Validation (it uses Validation and Quality)
    target_val_ev = "ev_evals = s.scalars(select(EnterpriseValidationResourceEvaluationRow)).all()"
    replacement_val_ev = "ev_evals = s.scalars(select(EnterpriseValidationResourceEvaluationRow).order_by(EnterpriseValidationResourceEvaluationRow.id.desc()).limit(100)).all()"
    content = content.replace(target_val_ev, replacement_val_ev)

    with open('api/scoring.py', 'w', encoding='utf-8') as f:
        f.write(content)
        print("Successfully patched api/scoring.py")

if __name__ == '__main__':
    patch_scoring()
