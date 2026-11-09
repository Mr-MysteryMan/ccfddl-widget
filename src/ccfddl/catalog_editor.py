"""Validated catalog edits shared by the settings controls."""

from dataclasses import replace
from uuid import uuid4

from .config import Conference, validate_catalog


class CatalogEditor:
    def __init__(self, catalog):
        self.catalog = catalog

    def commit(self, **changes):
        self.catalog = validate_catalog(replace(self.catalog, **changes))

    def add_category(self, code, label, color):
        if code in self.catalog.categories:
            raise ValueError('该 category 已存在。')
        self.commit(categories={**self.catalog.categories, code: label},
                    category_colors={**self.catalog.category_colors, code: self.palette(color)})

    def edit_category(self, old, code, label, color):
        if code != old and code in self.catalog.categories:
            raise ValueError('该 category 已存在。')
        categories = {code if key == old else key: label if key == old else value
                      for key, value in self.catalog.categories.items()}
        colors = {key: value for key, value in self.catalog.category_colors.items() if key != old}
        colors[code] = self.palette(color)
        self.commit(categories=categories, category_colors=colors,
                    conferences=tuple(replace(c, category=code) if c.category == old else c
                                      for c in self.catalog.conferences))

    def remove_category(self, code):
        if any(c.category == code for c in self.catalog.conferences):
            raise ValueError('请先将该分类中的会议移到其他分类，或删除这些会议。')
        if len(self.catalog.categories) <= 1:
            raise ValueError('请至少保留一个分类。')
        self.commit(categories={key: value for key, value in self.catalog.categories.items() if key != code},
                    category_colors={key: value for key, value in self.catalog.category_colors.items() if key != code})

    @staticmethod
    def palette(color):
        if len(color) != 7 or not color.startswith('#'):
            raise ValueError('请选择有效颜色。')
        try:
            red, green, blue = (int(color[index:index + 2], 16) for index in (1, 3, 5))
        except ValueError as error:
            raise ValueError('请选择有效颜色。') from error
        foreground = '#102a49' if 0.299 * red + 0.587 * green + 0.114 * blue > 175 else '#ffffff'
        return {'bg': color.lower(), 'fg': foreground}

    def add_tag(self, tag):
        tag = tag.strip()
        if not tag or tag in self.catalog.tags:
            raise ValueError('tag 不能为空，也不能重复。')
        self.commit(tags=(*self.catalog.tags, tag))

    def rename_tag(self, old, new):
        new = new.strip()
        if not new or (new != old and new in self.catalog.tags):
            raise ValueError('tag 不能为空，也不能重复。')
        self.commit(tags=tuple(new if tag == old else tag for tag in self.catalog.tags),
                    conferences=tuple(replace(c, tag=new) if c.tag == old else c for c in self.catalog.conferences))

    def remove_tag(self, tag):
        if any(c.tag == tag for c in self.catalog.conferences):
            raise ValueError('请先修改使用该 tag 的会议。')
        self.commit(tags=tuple(value for value in self.catalog.tags if value != tag))

    def add_conference(self, title, category, tag, source=''):
        conference = Conference('custom-' + uuid4().hex, title, category, tag, source, core_rank='')
        self.commit(conferences=(*self.catalog.conferences, conference))
        return conference.id

    def edit_conference(self, key, title, category, tag, source=''):
        old = next(c for c in self.catalog.conferences if c.id == key)
        rank = old.core_rank if title == old.title and source == old.source else ''
        conference = replace(old, title=title, category=category, tag=tag, source=source, core_rank=rank)
        self.commit(conferences=tuple(conference if c.id == key else c for c in self.catalog.conferences))

    def remove_conference(self, key):
        self.commit(conferences=tuple(c for c in self.catalog.conferences if c.id != key))
