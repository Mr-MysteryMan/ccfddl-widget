"""Resolve user-entered conference acronyms to upstream data files."""

from pathlib import PurePosixPath

import requests

TREE_API = 'https://api.github.com/repos/ccfddl/ccf-deadlines/git/trees/main?recursive=1'


class ConferenceNotFound(ValueError):
    pass


def conference_paths() -> list[str]:
    response = requests.get(TREE_API, headers={'User-Agent': 'CCFDDL-Desktop-Widget'}, timeout=(10, 20))
    response.raise_for_status()
    document = response.json()
    if not isinstance(document, dict) or document.get('truncated') or not isinstance(document.get('tree'), list):
        raise ValueError('Unable to read the complete conference index')
    return [entry['path'] for entry in document['tree'] if isinstance(entry, dict)
            and entry.get('type') == 'blob' and isinstance(entry.get('path'), str)
            and entry['path'].startswith('conference/')
            and len(PurePosixPath(entry['path']).parts) == 3
            and PurePosixPath(entry['path']).suffix in ('.yml', '.yaml')]


def normalize_name(value: str) -> str:
    return ''.join(character for character in value.casefold() if character.isalnum())


def resolve_source(conference, paths: list[str]) -> str:
    name = normalize_name(conference.title)
    short_name = name
    for prefix in ('ieee', 'acm', 'cvf', 'usenix'):
        if short_name.startswith(prefix) and len(short_name) > len(prefix):
            short_name = short_name[len(prefix):]
    aliases = {'neurips': 'nips', 'usenixsecurity': 'uss', 'sigkdd': 'kdd'}
    names = {name, short_name, aliases.get(name, name), aliases.get(short_name, short_name)}
    matches = [path for path in paths if normalize_name(PurePosixPath(path).stem) in names]
    if len(matches) > 1:
        preferred = [path for path in matches if PurePosixPath(path).parts[1] == conference.category]
        if len(preferred) == 1:
            return preferred[0]
        raise ConferenceNotFound('会议简称对应多个数据文件，请在编辑会议时指定数据路径。')
    if not matches:
        raise ConferenceNotFound('数据源中未找到该会议，请检查会议简称或指定数据路径。')
    return matches[0]
