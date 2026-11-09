# CCFDDL Desktop Widget

English | [简体中文](README-zh.md)

A Windows desktop widget for conference deadlines, with countdowns, conference filtering, and editable categories, tags, and conferences.

## 1. Quick Start and Packaging

If you already have the EXE, run it directly. The default conference list is bundled with the application. To edit the default list through a file, place `conferences.yaml` alongside the EXE. An internet connection is required to load the data on first use.

### Run from Source

Requires Python 3.10 or later. Run the following commands from the project root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe src/main.py
```

### Build the EXE

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m PyInstaller CCFDDLWidget.spec
.\.venv\Scripts\python.exe tests/smoke_exe.py dist/CCFDDLWidget.exe
```

The output is `dist/CCFDDLWidget.exe`.

To launch the widget at Windows startup, create a shortcut to the EXE, press `Win + R`, enter `shell:startup`, and place the shortcut in the folder that opens.

## 2. Settings

Right-click the desktop widget and select **Settings (设置…)**. The settings window has three tabs:

| Tab | Features |
| --- | --- |
| Conferences (会议) | Choose which conferences to display; search, select all, clear all, and add, edit, or delete conferences |
| category | Set category codes, names, and colors; renaming a category also updates its conferences |
| tag | Add, rename, or delete tags; renaming a tag also updates the conferences that use it |

To add a conference, enter its acronym, such as `WWW` or `KDD`, and choose a category and tag. Leave the data path empty for automatic lookup. If an acronym is ambiguous, specify the upstream file path, such as `conference/DB/www.yml`. Manually added conferences may have other CORE ranks; the widget displays the ranks reported by the data source.

Conference data refreshes every 24 hours, and countdowns update every minute. You can also refresh manually from the right-click menu. A `~` marks an estimate based on a past edition; check the conference's official call for papers for confirmed dates. If a conference fails to download, its previously loaded, unexpired data is retained. Hover over the status text to view errors.

Left-click a conference row to open its website. Drag an empty area to move the widget, or use the right-click menu to exit.

## 3. Default Conference List

The default list contains 31 conferences selected using the upstream `rank.core: A*` label. CCF ranks are displayed separately. Conferences are grouped as follows:

| Category | Name / Color | Conferences |
| --- | --- | --- |
| AI | Artificial Intelligence / Blue | AAAI, ACL, COLT, CVPR, ECCV, EMNLP, ICCV, ICLR, ICML, IJCAI, KR, NeurIPS |
| RO | Robotics / Orange | ICRA, RSS |
| CM | Computing Methodologies / Gray; tag: AP | AAMAS, ICAPS |
| SC | Network and System Security / Red | CCS, CRYPTO, EUROCRYPT, NDSS, S&P, USENIX Security |
| SE | Software Engineering / Systems / Programming Languages / Green | ASE, CAV, FSE, ICSE, LICS, OSDI, PLDI, POPL, SOSP |

Each conference record uses the following main fields:

```yaml
- id: icml
  title: ICML
  category: AI
  tag: ML
  source: conference/AI/icml.yml
```

## 4. Data Sources

Conference data comes from [ccfddl/ccf-deadlines](https://github.com/ccfddl/ccf-deadlines). You can also visit the [CCF Deadlines website](https://ccfddl.com/).

Thanks to **the ccfddl project and all its maintainers and contributors** for maintaining and updating the conference data.
