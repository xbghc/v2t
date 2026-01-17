"""配置管理 - 优先使用环境变量，回退到 JSON 配置文件"""

import json
import os
from dataclasses import dataclass
from pathlib import Path

CONFIG_PATH = Path.home() / ".config" / "v2t" / "config.json"

# 环境变量映射
ENV_MAPPING = {
    "groq_api_key": "GROQ_API_KEY",
    "deepseek_api_key": "DEEPSEEK_API_KEY",
    "xiazaitool_token": "XIAZAITOOL_TOKEN",
    "dashscope_api_key": "DASHSCOPE_API_KEY",
}


@dataclass
class Settings:
    """应用配置"""

    # API Keys
    groq_api_key: str = ""
    deepseek_api_key: str = ""
    xiazaitool_token: str = ""
    dashscope_api_key: str = ""  # 阿里云百炼 API Key（TTS 服务）

    # API URLs (固定值)
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_whisper_model: str = "whisper-large-v3"
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    xiazaitool_api_url: str = "https://api.xiazaitool.com/api/parseVideoUrl"

    # 用户可配置
    max_video_duration: int = 7200  # 秒，默认 2 小时
    temp_dir: str = "/tmp/v2t"  # 临时文件目录

    @property
    def temp_path(self) -> Path:
        """临时文件目录"""
        path = Path(self.temp_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path


def load_config() -> dict:
    """加载配置文件"""
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return {}


def save_config(config: dict):
    """保存配置文件"""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(
        json.dumps(config, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


_settings: Settings | None = None


def get_settings() -> Settings:
    """获取配置（单例）- 环境变量优先，回退到配置文件"""
    global _settings
    if _settings is None:
        config = load_config()
        # 环境变量优先覆盖配置文件
        for field_name, env_name in ENV_MAPPING.items():
            env_value = os.environ.get(env_name)
            if env_value:
                config[field_name] = env_value
        # 只传入 Settings 支持的字段
        valid_fields = {f.name for f in Settings.__dataclass_fields__.values()}
        filtered_config = {k: v for k, v in config.items() if k in valid_fields}
        _settings = Settings(**filtered_config)
    return _settings
