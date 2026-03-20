#!/bin/bash
# Toggle MyAgent MCP for Kimi CLI

KIMI_DIR="${HOME}/.kimi"
MCP_CONFIG="${KIMI_DIR}/mcp.json"
MCP_WITH_MYAGENT="${KIMI_DIR}/mcp-with-myagent.json"
MCP_WITHOUT_MYAGENT="${KIMI_DIR}/mcp-no-myagent.json"

# 创建配置目录
mkdir -p "$KIMI_DIR"

# 创建带 myagent 的配置（如果不存在）
if [ ! -f "$MCP_WITH_MYAGENT" ]; then
    cat > "$MCP_WITH_MYAGENT" << 'EOF'
{
  "mcpServers": {
    "myagent": {
      "command": "python",
      "args": ["-m", "myagent.mcp_server"],
      "env": {
        "MYAGENT_DATA_DIR": "~/.local/share/myagent"
      }
    }
  }
}
EOF
    echo "Created: $MCP_WITH_MYAGENT"
fi

# 创建不带 myagent 的配置（如果不存在）
if [ ! -f "$MCP_WITHOUT_MYAGENT" ]; then
    cat > "$MCP_WITHOUT_MYAGENT" << 'EOF'
{
  "mcpServers": {}
}
EOF
    echo "Created: $MCP_WITHOUT_MYAGENT"
fi

# 检查当前状态
check_status() {
    if [ -f "$MCP_CONFIG" ]; then
        if grep -q "myagent" "$MCP_CONFIG" 2>/dev/null; then
            echo "enabled"
        else
            echo "disabled"
        fi
    else
        echo "none"
    fi
}

# 切换配置
toggle() {
    current=$(check_status)
    
    if [ "$current" = "enabled" ]; then
        # 禁用 myagent
        cp "$MCP_WITHOUT_MYAGENT" "$MCP_CONFIG"
        echo "❌ MyAgent disabled"
        echo "   Run 'kimi' to start without MyAgent"
    elif [ "$current" = "disabled" ]; then
        # 启用 myagent
        cp "$MCP_WITH_MYAGENT" "$MCP_CONFIG"
        echo "✅ MyAgent enabled"
        echo "   Run 'kimi' to start with MyAgent"
    else
        # 默认启用
        cp "$MCP_WITH_MYAGENT" "$MCP_CONFIG"
        echo "✅ MyAgent enabled (default)"
    fi
}

# 强制启用
enable_myagent() {
    cp "$MCP_WITH_MYAGENT" "$MCP_CONFIG"
    echo "✅ MyAgent enabled"
}

# 强制禁用
disable_myagent() {
    cp "$MCP_WITHOUT_MYAGENT" "$MCP_CONFIG"
    echo "❌ MyAgent disabled"
}

# 显示状态
show_status() {
    current=$(check_status)
    echo "Current MyAgent status: $current"
    
    if [ "$current" = "enabled" ]; then
        echo "  MyAgent will be loaded when you run 'kimi'"
    elif [ "$current" = "disabled" ]; then
        echo "  MyAgent will NOT be loaded when you run 'kimi'"
    else
        echo "  No MCP config found"
    fi
}

# 主逻辑
case "${1:-toggle}" in
    toggle|t)
        toggle
        ;;
    enable|e|on)
        enable_myagent
        ;;
    disable|d|off)
        disable_myagent
        ;;
    status|s)
        show_status
        ;;
    *)
        echo "Usage: $0 [toggle|enable|disable|status]"
        echo ""
        echo "Commands:"
        echo "  toggle   - Switch between enabled/disabled (default)"
        echo "  enable   - Enable MyAgent MCP"
        echo "  disable  - Disable MyAgent MCP"
        echo "  status   - Show current status"
        ;;
esac
