import sys

def patch_app_py():
    with open('api/app.py', 'r', encoding='utf-8') as f:
        content = f.read()
        
    # Patch 1: _score_row_to_rating
    target1 = """    from api.scoring import _sync_metrics_from_sub_metrics
    _sync_metrics_from_sub_metrics(m_dict, live_sub)
    from engine.score import composite
    _raw, w_dict, active_weights = composite(m_dict, settings.weights)"""
    
    replacement1 = """    from api.scoring import _sync_metrics_from_sub_metrics, _get_custom_weightages
    _sync_metrics_from_sub_metrics(m_dict, live_sub)
    from engine.score import composite
    custom_weights = _get_custom_weightages(s, row.agent_id)
    _raw, w_dict, active_weights = composite(m_dict, custom_weights if custom_weights else settings.weights)"""
    
    if target1 in content:
        content = content.replace(target1, replacement1)
        print("Patched _score_row_to_rating")
    else:
        print("Could not find target1")
        
    # Patch 2: ratings
    target2 = """        # --- Apply Custom Weights dynamically ---
        agent_configs = repo.list_agent_configurations(s, agent.id)
        custom_weights = weights.copy()
        for c in agent_configs:
            if c.configuration_key.startswith("Weight_"):
                metric_char = c.configuration_key.split("_")[1][0].upper()
                try:
                    custom_weights[metric_char] = float(c.configuration_value) / 100.0
                except ValueError:
                    pass

        from engine.score import composite
        _raw, w_dict, active_weights = composite(m_dict, custom_weights)"""
        
    replacement2 = """        from api.scoring import _get_custom_weightages
        from engine.score import composite
        
        custom_w = _get_custom_weightages(s, agent.id)
        _raw, w_dict, active_weights = composite(m_dict, custom_w if custom_w else weights)"""
        
    if target2 in content:
        content = content.replace(target2, replacement2)
        print("Patched ratings()")
    else:
        print("Could not find target2")
        
    with open('api/app.py', 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == '__main__':
    patch_app_py()
