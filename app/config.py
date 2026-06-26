from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv


load_dotenv()


@dataclass(slots=True)
class AppConfig:
    access_key_id: str
    access_key_secret: str
    workspace_id: str
    region_id: str = "cn-beijing"
    default_index_id: str | None = None
    default_category_id: str | None = None

    @classmethod
    def from_env(cls) -> "AppConfig":
        access_key_id = os.getenv("BAILIAN_ACCESS_KEY_ID") or os.getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")
        access_key_secret = os.getenv("BAILIAN_ACCESS_KEY_SECRET") or os.getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")
        workspace_id = os.getenv("BAILIAN_WORKSPACE_ID") or os.getenv("WORKSPACE_ID")
        region_id = os.getenv("BAILIAN_REGION_ID", "cn-beijing")
        default_index_id = os.getenv("BAILIAN_INDEX_ID") or os.getenv("INDEX_ID") or os.getenv("IndexID")
        default_category_id = os.getenv("BAILIAN_CATEGORY_ID") or os.getenv("CATEGORY_ID") or os.getenv("CategoryID")

        missing = [
            name
            for name, value in {
                "BAILIAN_ACCESS_KEY_ID or ALIBABA_CLOUD_ACCESS_KEY_ID": access_key_id,
                "BAILIAN_ACCESS_KEY_SECRET or ALIBABA_CLOUD_ACCESS_KEY_SECRET": access_key_secret,
                "BAILIAN_WORKSPACE_ID or WORKSPACE_ID": workspace_id,
            }.items()
            if not value
        ]
        if missing:
            missing_text = ", ".join(missing)
            raise ValueError(f"Missing required environment variables: {missing_text}")

        return cls(
            access_key_id=access_key_id,
            access_key_secret=access_key_secret,
            workspace_id=workspace_id,
            region_id=region_id,
            default_index_id=default_index_id,
            default_category_id=default_category_id,
        )


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    return AppConfig.from_env()
