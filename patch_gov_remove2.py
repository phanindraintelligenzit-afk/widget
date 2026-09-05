with open('dpi_ls/governance_resource_evaluation_service.py', 'r', encoding='utf-8') as f:
    c = f.read()

c = c.replace('Register the 3 governance resources: Open Policy Agent, Microsoft Presidio, and Detect-Secrets.', 'Register the 3 governance resources: Open Policy Agent, Keycloak, and OpenMetadata.')

with open('dpi_ls/governance_resource_evaluation_service.py', 'w', encoding='utf-8') as f:
    f.write(c)
