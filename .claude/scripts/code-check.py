#!/usr/bin/env python3
import json
import sys
import subprocess
# 从 stdin 读取输入
try:
    input_data = json.load(sys.stdin)
except json.JSONDecodeError as e:
    print(f"Error: Invalid JSON input: {e}", file=sys.stderr)
    sys.exit(1)

def accept():
    output = {}
    print(json.dumps(output, ensure_ascii=False))
    sys.exit(0)

def reject(reason):
    output = {
        "decision": 'block',
        "reason": reason
    }
    print(json.dumps(output, ensure_ascii=False))
    sys.exit(0)

# 运行 lint 和 test
try:
    lint_result = subprocess.run(
        ["make", "lint"], 
        capture_output=True, 
        text=True
    )
    
    if lint_result.returncode != 0:
        reject(f"Lint 失败:\n{lint_result.stdout}\n{lint_result.stderr}")
    
    test_result = subprocess.run(
        ["make", "test"], 
        capture_output=True, 
        text=True
    )
    
    if test_result.returncode != 0:
        reason = f"Test 失败:\n{test_result.stdout}\n{test_result.stderr}"
        reject(reason)
    
    # 全部通过
    accept()

except Exception as e:
    reject(f"检查过程中出现错误: {e}")