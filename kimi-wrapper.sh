#!/bin/bash
# Kimi wrapper with optional MyAgent

KIMI_MCP_CONFIG="${HOME}/.kimi/mcp.json"
KIMI_MCP_BACKUP="${HOME}/.kimi/mcp.json.bak"

# 检查是否需要禁用 myagent
if [ "$1" = "--no-myagent" ] || [ "$1" = "-n" ]; then
    shift
    
    # 备份并禁用 myagent
    if [ -f "$KIMI_MCP_CONFIG" ]; then
        cp "$KIMI_MCP_CONFIG" "$KIMI_MCP_BACKUP"
        # 使用 Python 或 sed 禁用 myagent
        python3 << 'PYEOF'
import json, sys, os
config_path = os.path.expanduser("~/.kimi/mcp.json")
try:
    with open(config_path, 'r') as f:
        config = json.load(f)
    if 'mcpServers' in config and 'myagent' in config['mcpServers']:
        config['mcpServers']['myagent']['disabled'] = True
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        print("MyAgent disabled for this session")
except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
PYEOF
    fi
    
    # 启动 kimi
    kimi "$@"
    
    # 恢复配置
    if [ -f "$KIMI_MCP_BACKUP" ]; then
        mv "$KIMI_MCP_BACKUP" "$KIMI_MCP_CONFIG"
        echo "MyAgent config restored"
    fi
else
    # 正常启动 kimi（使用 myagent）
    exec kimi "$@"
fi
