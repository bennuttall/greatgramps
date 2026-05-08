from functools import cache
from pathlib import Path

import yaml
from pydantic import BaseModel, FilePath
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_prefix='greatgramps_')

    config: FilePath


class Config(BaseModel):
    root_path: Path
    db_path: Path
    me: str
    templates_dir: Path = Path('templates')
    output_dir: Path = Path('www')

    def model_post_init(self, _context):
        root = self.root_path
        for attr in ('db_path', 'templates_dir', 'output_dir'):
            p = getattr(self, attr)
            if not p.is_absolute():
                setattr(self, attr, root / p)


@cache
def get_config() -> Config:
    settings = Settings()
    with open(settings.config) as f:
        data = yaml.safe_load(f)
    data['root_path'] = settings.config.parent.absolute()
    return Config.model_validate(data)
