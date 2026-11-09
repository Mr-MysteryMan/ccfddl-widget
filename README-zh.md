# CCFDDL Desktop Widget

[English](README.md) | 简体中文

Windows 桌面会议截止日期小组件，支持倒计时、会议筛选，以及自定义 category、tag 和会议。

## 1. 快速使用与打包

已有 EXE 时直接运行即可。程序内置默认会议列表；如需通过文件修改默认列表，可将 `conferences.yaml` 放在 EXE 同一目录。首次加载数据需要联网。

### 从源码运行

需要 Python 3.10 或更高版本。以下命令均在项目根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe src/main.py
```

### 打包为 EXE

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m PyInstaller CCFDDLWidget.spec
.\.venv\Scripts\python.exe tests/smoke_exe.py dist/CCFDDLWidget.exe
```

输出为 `dist/CCFDDLWidget.exe`。
如需开机自启动，为 EXE 创建快捷方式，按 `Win + R` 输入 `shell:startup`，将快捷方式放入打开的文件夹。

## 2. 设置

在桌面小组件点击鼠标右键，选择 **设置…**。设置分为三个页签：

| 页签 | 功能 |
| --- | --- |
| 会议 | 勾选显示的会议，支持搜索、全选、全不选，以及添加、编辑、删除会议 |
| category | 设置分类代码、名称和颜色；重命名分类时同步更新所属会议 |
| tag | 添加、重命名、删除标签；重命名时同步更新使用该标签的会议 |

添加会议时输入简称，例如 `WWW`、`KDD`，并选择 category、tag。数据路径可以留空，由后台自动查询；简称有歧义时，可指定上游文件路径，例如 `conference/DB/www.yml`。手动新增的会议允许其他 CORE 等级，界面显示数据源中的实际等级。

数据每 24 小时更新一次，倒计时每分钟更新，也可通过右键菜单手动刷新。`~` 表示按历史日期推算的估计值，应以会议官方 CFP 为准。部分会议下载失败时，会保留其上次加载且尚未过期的数据；悬停状态文字可查看错误。

左键点击会议行打开会议链接，拖动空白区域移动小组件，右键菜单中可退出程序。

## 3. 默认会议列表

默认列表共 31 个会议，按上游数据的 `rank.core: A*` 收录，CCF 等级另外显示。展示分类如下：

| category | 名称 / 颜色 | 会议 |
| --- | --- | --- |
| AI | 人工智能 / 蓝色 | AAAI、ACL、COLT、CVPR、ECCV、EMNLP、ICCV、ICLR、ICML、IJCAI、KR、NeurIPS |
| RO | 机器人 / 橙色 | ICRA、RSS |
| CM | 计算机方法论 / 灰色，tag 为 AP | AAMAS、ICAPS |
| SC | 网络与系统安全 / 红色 | CCS、CRYPTO、EUROCRYPT、NDSS、S&P、USENIX Security |
| SE | 软件工程 / 系统 / 程序语言 / 绿色 | ASE、CAV、FSE、ICSE、LICS、OSDI、PLDI、POPL、SOSP |

每条会议记录的主要字段为：

```yaml
- id: icml
  title: ICML
  category: AI
  tag: ML
  source: conference/AI/icml.yml
```

## 4. 数据来源

会议数据来自 [ccfddl/ccf-deadlines](https://github.com/ccfddl/ccf-deadlines)，也可访问其网站 [CCF Deadlines](https://ccfddl.com/)。
感谢 **ccfddl 项目及所有维护者、贡献者**持续整理和更新会议数据。
