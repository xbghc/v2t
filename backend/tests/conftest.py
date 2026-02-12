"""测试配置"""

import os

# MongoDB 测试配置（无默认值）
MONGO_URI = os.environ.get("TEST_MONGODB_URI", "")
MONGO_DB = os.environ.get("TEST_MONGODB_DATABASE", "")
