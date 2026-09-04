from functools import cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, FilePath, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

NavPage = Literal[
    'home', 'my-tree', 'me', 'explore', 'people', 'places', 'events', 'census', 'cemeteries', 'birthdays', 'surnames'
]

DEFAULT_NAV_PAGES: list[NavPage] = [
    'home', 'my-tree', 'me', 'explore', 'people', 'places', 'events', 'census', 'cemeteries', 'birthdays', 'surnames'
]

ExcludablePage = Literal[
    'explore', 'people', 'places', 'events', 'census', 'cemeteries', 'birthdays', 'surnames',
    'ancestor-records', 'census-records',
]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_prefix='greatgramps_')

    config: FilePath


class Config(BaseModel):
    root_path: Path
    db_path: Path
    roots: list[str]
    ancestry_tree_id: str | None = None
    templates_dir: Path | None = None
    static_dir: Path | None = None
    output_dir: Path = Path('www')
    nav_pages: list[NavPage] = DEFAULT_NAV_PAGES
    exclude_pages: list[ExcludablePage] = []
    site_title: str = 'Family tree'
    site_root: str = '/'

    @field_validator('site_root')
    @classmethod
    def normalise_site_root(cls, v: str) -> str:
        if not v.startswith('/'):
            v = '/' + v
        if not v.endswith('/'):
            v = v + '/'
        return v

    @property
    def validated_db_path(self) -> Path:
        if not self.db_path.exists():
            raise FileNotFoundError(f"Gramps database not found: {self.db_path}")
        return self.db_path

    def model_post_init(self, _context):
        root = self.root_path
        for attr in ('db_path', 'output_dir'):
            p = getattr(self, attr)
            if not p.is_absolute():
                setattr(self, attr, root / p)
        for attr in ('templates_dir', 'static_dir'):
            p = getattr(self, attr)
            if p is not None and not p.is_absolute():
                setattr(self, attr, root / p)


@cache
def get_config() -> Config:
    settings = Settings()
    with open(settings.config) as f:
        data = yaml.safe_load(f)
    data['root_path'] = settings.config.parent.absolute()
    return Config.model_validate(data)