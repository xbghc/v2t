"""跨模块共享常量。"""

# 对外 API 版本前缀。版本号的唯一来源：
#   - main.py 用它统一挂载对外 router
#   - response.py 用它拼接返回给客户端的 stream_url / download_url
# 开 v2 时改这一处（或新增 API_V2_PREFIX 并存）。
# 内部端点（/api/admin、/api/diag、/api/metrics）不走这个前缀，不纳入版本契约。
API_V1_PREFIX = "/api/v1"
