#!/usr/bin/env bash
# IRIS v7.0 Health Check Script

python3 -c "
from core.bootstrap import bootstrap_all, shutdown
import json

c = bootstrap_all(data_dir='/mnt/agents/output/iris_v7/data', max_workers=2)
health = c.registry.health_check_all()

print('═' * 60)
print('  AEVIBRON AGENT CORPS — HEALTH CHECK')
print('═' * 60)

for name, h in health.items():
    status_icon='✅' if h.get('status') == 'idle' else '🔄' if h.get('status') == 'busy' else '❌'
    print(f'{status_icon} {name:12} | status={h.get("status", "?"):12} | load={h.get("load", 0):.2f} | domain={h.get("domain", "?")}')

stats = c.registry.get_stats()
print('─' * 60)
print(f'Total: {stats["total_agents"]} agents | Available: {stats["available_agents"]}')
print('═' * 60)

shutdown(c)
"
