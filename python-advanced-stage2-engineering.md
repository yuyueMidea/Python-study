# Python 进阶 · 阶段 2：工程化能力（第 7～10 周）

> **目标**：从"能跑就行的脚本"到"别人能安装、能运行、能维护、能放心修改的项目"。
> **适合人群**：已完成阶段 1（语言深度），或已有较扎实的 Python 语言基础，做过爬虫和 PyQt 项目的开发者。
> **时间安排**：每周 8～10 小时（阅读 2h + 编码 5h + 重构 1h + 复盘 1～2h）。
> **核心思路**：本阶段**没有新项目**，所有内容都落在**同一个旧项目的改造**上（推荐用你的爬虫项目）。
> **工具版本说明**：工具更新很快（尤其是 `uv`、`ruff`、GitHub Actions 的 action 版本号），文中的配置以"思路正确"为准，动手前请核对各工具官方文档的最新写法。

---

## 目录

- [0. 使用说明](#0-使用说明)
- [第 7 周：环境、依赖与项目结构](#第-7-周环境依赖与项目结构)
- [第 8 周：代码质量工具链、Git 协作与调试](#第-8-周代码质量工具链git-协作与调试)
- [第 9 周：自动化测试](#第-9-周自动化测试)
- [第 10 周：打包、Docker、CI 与综合项目](#第-10-周打包dockerci-与综合项目)
- [阶段验收清单](#阶段验收清单)
- [常见误区与建议](#常见误区与建议)
- [资源汇总](#资源汇总)

---

## 0. 使用说明

### 为什么工程化是"分水岭"

业余脚本与专业项目的差别，不在于算法多聪明，而在于：

| 维度 | 业余脚本 | 工程化项目 |
|---|---|---|
| 运行 | "在我电脑上能跑" | 任何人一条命令就能装好并运行 |
| 依赖 | 想起什么装什么 | 版本锁定，可复现 |
| 修改 | 改一处怕坏三处 | 有测试兜底，改完一键验证 |
| 协作 | 文件夹互相拷贝 | Git 分支 + 代码审查 |
| 质量 | 靠肉眼 | 工具自动检查格式、类型、潜在 bug |
| 发布 | 发一个压缩包 | 自动构建、自动发布 |
| 排错 | `print` 满天飞 | 日志、断点、性能分析 |

### 本阶段的统一素材：改造一个旧项目

**请先选定一个"改造对象"**，推荐你写过的、有一定规模的爬虫项目（200 行以上，最好有解析、存储逻辑）。整个阶段将围绕它做五件事：

```
第 7 周：把它整理成标准的 src 布局 + pyproject.toml + 可配置
第 8 周：接入 ruff / mypy / pre-commit，规范 Git 历史
第 9 周：为核心逻辑补上单元测试和集成测试
第10 周：打包、Docker 化、GitHub Actions 自动跑质量检查
```

> **备选**：如果你的爬虫项目太小，可以用阶段 1 的 `organizer` 工具，或选一个 PyQt 工具作为第二个改造对象（第 9、10 周有专门的 PyQt 小节）。

### 每周固定流程

| 环节 | 时长 | 内容 |
|---|---|---|
| 阅读 | 2h | 官方文档 + 书籍对应章节 |
| 动手 | 5h | 按本周清单一步步改造项目，并提交到 Git |
| 对照 | 1h | 阅读一个优秀开源项目的对应配置（如 `httpx`、`ruff`、`pydantic`） |
| 复盘 | 1～2h | 回答自测题，记录"改造前 / 改造后"的对比 |

### 学习原则

1. **每一步都要提交**：把改造过程拆成小提交，提交信息写清楚，这本身就是练习。
2. **先让工具报错，再逐条修**：引入 `ruff`、`mypy` 时一定会冒出一堆问题，这是价值所在。
3. **不求一次完美**：先让流程跑通，再逐步收紧规则。
4. **一切可自动化的，都不要靠记忆**：格式化、检查、测试、发布，全部自动化。

---

## 第 7 周：环境、依赖与项目结构

### 本周目标

- 彻底理解虚拟环境与依赖管理，能做到"新机器一条命令复现环境"
- 掌握 `pyproject.toml`，理解它取代 `setup.py` / `requirements.txt` 的原因
- 使用 `uv`（或 Poetry）管理项目
- 把项目整理成规范的 `src/` 布局
- 做到"代码与配置分离"，不把密钥写进代码

### 7.1 为什么需要虚拟环境

问题：全局安装所有包，项目 A 需要 `requests==2.28`，项目 B 需要 `requests==2.32`，必然冲突。

```bash
# 标准库方式
python -m venv .venv
source .venv/bin/activate          # Linux / macOS
.venv\Scripts\activate             # Windows (cmd / PowerShell)

pip install httpx
pip freeze > requirements.txt      # 缺点：把间接依赖也一起冻结，难以区分"我要的"与"被带来的"
deactivate
```

**要点**

- 虚拟环境本质是一个**独立的目录**，包含自己的解释器链接和 `site-packages`。
- **虚拟环境不要提交到 Git**，也不要移动或复制它，需要时重建。
- 每个项目一个虚拟环境，通常放在项目根目录的 `.venv/`。
- 用 `which python`（Windows：`where python`）确认当前用的是哪个解释器。

### 7.2 依赖管理的现代做法：`uv`

`uv` 是目前速度最快、一体化程度最高的工具，可同时替代 `pip`、`venv`、`pip-tools`、部分 `pyenv` 和 `poetry` 的功能。（Poetry、PDM、Hatch 同样可用，思想一致。）

```bash
# 安装（参考官方文档，选择适合你系统的方式）
pip install uv            # 最简单，也可用官方安装脚本 / 包管理器

# 创建项目
uv init crawler-kit --package        # 带 src 布局的包项目
cd crawler-kit

# 管理 Python 版本
uv python install 3.12
uv python pin 3.12

# 添加依赖
uv add httpx parsel pydantic
uv add --dev pytest pytest-cov ruff mypy pre-commit   # 开发依赖

# 同步环境（按锁文件安装）
uv sync

# 运行命令（自动使用项目环境，无需手动激活）
uv run pytest
uv run python -m crawler

# 升级与移除
uv lock --upgrade-package httpx
uv remove parsel
```

**两个关键文件**

| 文件 | 作用 | 是否提交 Git |
|---|---|---|
| `pyproject.toml` | 声明"我需要什么"（范围） | ✅ |
| `uv.lock` | 记录"实际装了什么"（精确版本 + 哈希） | ✅（应用/项目必须提交） |

**理解"声明"与"锁定"的区别**：`httpx>=0.27` 是声明；`httpx==0.27.2` 加哈希是锁定。锁文件保证**团队成员、CI、生产环境装出完全一样的依赖**。

### 7.3 版本约束的写法

| 写法 | 含义 | 使用场景 |
|---|---|---|
| `httpx>=0.27` | 不低于该版本 | 通用下限 |
| `httpx>=0.27,<1.0` | 限定在大版本内 | 推荐，避免大版本破坏 |
| `httpx~=0.27.0` | 兼容版本（`>=0.27.0, ==0.27.*`） | 谨慎依赖时 |
| `httpx==0.27.2` | 精确版本 | 一般只出现在锁文件里 |

**原则**

- **库**（给别人用）：约束要宽松，避免和使用者的其他依赖冲突。
- **应用**（自己部署）：约束可以较紧，并提交锁文件。
- 区分**运行依赖**与**开发依赖**（测试、检查工具不应打进生产环境）。
- 定期审计：`pip-audit` 检查已知漏洞；用 Dependabot / Renovate 自动提升级 PR。

### 7.4 `pyproject.toml` 详解

这是现代 Python 项目的"身份证"，所有工具的配置集中在这里。

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "crawler-kit"
version = "0.1.0"
description = "A small, well-tested web crawling toolkit"
readme = "README.md"
requires-python = ">=3.11"
license = { text = "MIT" }
authors = [{ name = "Your Name", email = "you@example.com" }]
dependencies = [
    "httpx>=0.27,<1.0",
    "parsel>=1.9",
    "pydantic>=2.7,<3.0",
    "pydantic-settings>=2.3",
]

[project.optional-dependencies]       # 可选功能（extras）：pip install crawler-kit[browser]
browser = ["playwright>=1.45"]

[project.scripts]                     # 安装后生成命令行命令 `crawler`
crawler = "crawler.cli:main"

[dependency-groups]                   # 开发依赖组（PEP 735，uv 支持）
dev = [
    "pytest>=8",
    "pytest-cov>=5",
    "respx>=0.21",
    "mypy>=1.10",
    "ruff>=0.5",
    "pre-commit>=3.7",
]

[tool.hatch.build.targets.wheel]
packages = ["src/crawler"]

# ——以下为各工具配置，后续几周会逐步补全——
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM", "C4", "PT", "RUF"]

[tool.mypy]
strict = true
python_version = "3.11"

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra --strict-markers"
```

**需要理解**

- `[build-system]`：告诉安装工具"怎么构建我"（构建后端：hatchling / setuptools / flit / uv_build 等）。
- `[project]`：项目元数据与依赖（遵循 PEP 621，所有工具通用）。
- `[project.scripts]`：**入口点（entry points）**，让 `pip install` 后直接获得命令行命令。
- `[tool.*]`：各个工具各自的配置段落。

### 7.5 项目结构：`src/` 布局

```
crawler-kit/
├── pyproject.toml
├── uv.lock
├── README.md
├── LICENSE
├── .gitignore
├── .env.example               # 配置模板（可提交）；真正的 .env 不提交
├── .pre-commit-config.yaml    # 第 8 周
├── Dockerfile                 # 第 10 周
├── .github/workflows/ci.yml   # 第 10 周
├── src/
│   └── crawler/
│       ├── __init__.py
│       ├── __main__.py        # 支持 python -m crawler
│       ├── cli.py             # 命令行入口，只做参数解析与调度
│       ├── settings.py        # 配置（pydantic-settings）
│       ├── errors.py          # 自定义异常
│       ├── models.py          # 数据模型（pydantic / dataclass）
│       ├── fetcher.py         # 网络请求层：限速、重试、代理
│       ├── parsers/           # 解析层：纯函数，输入 HTML 输出数据
│       │   ├── __init__.py
│       │   └── example_site.py
│       ├── storage.py         # 存储层：SQLite / 文件 / 数据库
│       └── service.py         # 业务编排：把 fetch → parse → store 串起来
└── tests/
    ├── conftest.py
    ├── fixtures/              # 保存的真实 HTML 样本
    ├── test_parsers.py
    ├── test_fetcher.py
    └── test_service.py
```

**为什么用 `src/` 布局？**

- 防止测试时意外导入"项目根目录里的源码"，而不是"已安装的包"，这样能提早暴露打包错误。
- 业界主流做法（`httpx`、`pydantic`、`attrs` 等均采用）。

**为什么这样分层？**

| 层 | 职责 | 为什么独立 |
|---|---|---|
| `fetcher` | 只管"取网页" | 可替换（同步/异步/浏览器），测试时可替身 |
| `parsers` | **纯函数**：HTML → 数据 | 不依赖网络，最容易测试 |
| `storage` | 只管"存数据" | 可从 SQLite 换成 PostgreSQL |
| `service` | 编排流程 | 业务逻辑集中，便于测试与复用 |
| `cli` | 参数 → 调用 service | 薄薄一层，不放业务逻辑 |

> 这就是阶段 1 学到的"组合与依赖注入"的落地。依赖方向应当是：`cli → service → (fetcher / parsers / storage)`，**下层不能反向依赖上层**。

**导入规范**

```python
# 包内部使用绝对导入（推荐）
from crawler.models import Article
from crawler.parsers import parse_article

# 避免：循环导入。出现时说明分层有问题，应把共用类型提取到 models.py
```

**`__main__.py`**

```python
from crawler.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
```

### 7.6 配置管理：代码与配置分离

遵循"十二要素应用"的原则：**配置放在环境里**，同一份代码在开发、测试、生产环境用不同配置。

```python
# src/crawler/settings.py
from functools import lru_cache
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="CRAWLER_",
        extra="ignore",
    )

    db_url: str = "sqlite:///data/crawler.db"
    request_timeout: float = 10.0
    max_retries: int = 3
    rate_limit_per_sec: float = 2.0
    proxy: str | None = None
    user_agent: str = "crawler-kit/0.1 (+https://example.com/bot)"
    api_token: SecretStr | None = None       # SecretStr：打印时显示 **********，防止日志泄露
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

```bash
# .env.example（提交到仓库，作为模板）
CRAWLER_DB_URL=sqlite:///data/crawler.db
CRAWLER_REQUEST_TIMEOUT=10
CRAWLER_PROXY=
CRAWLER_API_TOKEN=
```

```gitignore
# .gitignore 中必须包含
.env
.venv/
__pycache__/
*.pyc
.mypy_cache/
.ruff_cache/
.pytest_cache/
.coverage
dist/
build/
*.egg-info/
data/
```

**配置读取优先级（pydantic-settings 默认）**：环境变量 > `.env` 文件 > 代码默认值。

**安全红线**

- **永远不要把密钥、Cookie、令牌提交到 Git**。一旦提交过，即使删除也在历史里，必须**吊销并重新生成**。
- 误提交后补救：立即吊销密钥；必要时使用 `git filter-repo` 清理历史（并通知协作者）。
- 可以在提交前用 `gitleaks` 等工具扫描（第 8 周 pre-commit 可集成）。

### 7.7 README：项目的门面

一个合格的 README 至少包含：

```markdown
# 项目名
一句话说明它做什么。

## 特性
- ...

## 快速开始
​```bash
uv sync
cp .env.example .env
uv run crawler --help
​```

## 配置
（表格列出各环境变量及默认值）

## 开发
​```bash
uv run pytest
uv run ruff check .
uv run mypy src
​```

## 项目结构 / 设计说明
## License
```

**检验标准**：让一个没见过项目的朋友，**只看 README** 能在 5 分钟内把项目跑起来。

### 7.8 本周练习

1. **练习 A（必做）**：把旧项目迁移成 `src/` 布局 + `pyproject.toml` + `uv` 管理，并让 `uv run crawler --help` 能跑通。
2. **练习 B（必做）**：删掉 `.venv`，在一个**干净目录**里 `git clone` 项目并按 README 重建环境，检验可复现性。
3. **练习 C（必做）**：把所有硬编码（URL、超时、请求头、数据库路径、代理）提取到 `Settings`，补全 `.env.example`。
4. **练习 D**：为项目添加一个可选依赖组 `[browser]`，体验 extras 的安装方式。
5. **练习 E**：用 `uv tree` 查看依赖树，找出"间接依赖"并理解它们的来源；用 `pip-audit` 扫描一次漏洞。
6. **练习 F**：阅读 `httpx` 或 `pydantic` 仓库的 `pyproject.toml`，列出 3 个你原来没见过的配置项并弄懂含义。

### 7.9 自测题

- `pyproject.toml` 与 `uv.lock`（或 `poetry.lock`）各自的作用？应用项目是否要提交锁文件？
- `src/` 布局相比"代码平铺在根目录"解决了什么问题？
- 为什么不应该提交虚拟环境？
- `[project.scripts]` 是如何让包提供命令行命令的？
- 开发依赖与运行依赖为什么要分开？
- 密钥不小心提交到了 Git，应当怎么处理？

### 7.10 阅读

- Python Packaging User Guide（packaging.python.org）：*Writing your pyproject.toml*
- `uv` 官方文档：Projects、Dependencies、Locking
- *The Twelve-Factor App*：Config 一节
- pydantic-settings 官方文档
- 《Architecture Patterns with Python》第 1～2 章（分层与依赖方向）

---

## 第 8 周：代码质量工具链、Git 协作与调试

### 本周目标

- 配置 `ruff`（检查 + 格式化）与 `mypy`/`pyright`，让质量检查自动化
- 用 `pre-commit` 在提交前拦截问题
- 掌握团队协作的 Git 工作流
- 学会日志、断点调试与性能分析，告别"满屏 print"

### 8.1 代码检查与格式化：`ruff`

`ruff` 一个工具同时替代 `flake8`、`isort`、`pyupgrade`、`black`（格式化）等。

```bash
uv run ruff check .              # 检查
uv run ruff check . --fix        # 自动修复可修复的问题
uv run ruff format .             # 格式化（兼容 black 风格）
uv run ruff format --check .     # 仅检查是否已格式化（CI 常用）
```

**规则集合选择**（`pyproject.toml` 中 `[tool.ruff.lint] select`）

| 规则前缀 | 来源 | 检查内容 |
|---|---|---|
| `E` / `W` | pycodestyle | 代码风格 |
| `F` | pyflakes | 未使用的导入/变量、未定义名称 |
| `I` | isort | 导入排序 |
| `UP` | pyupgrade | 升级到新语法（如 `List[int]` → `list[int]`） |
| `B` | flake8-bugbear | 常见 bug 模式（如可变默认参数） |
| `SIM` | flake8-simplify | 可简化的代码 |
| `C4` | flake8-comprehensions | 推导式优化 |
| `PT` | flake8-pytest-style | pytest 写法规范 |
| `RUF` | ruff 自有 | 杂项 |
| `S` | flake8-bandit | 安全问题（可后期开启） |
| `ASYNC` | flake8-async | 异步代码问题 |

```toml
[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM", "C4", "PT", "RUF"]
ignore = ["E501"]                          # 行长度交给 formatter 处理

[tool.ruff.lint.per-file-ignores]
"tests/*" = ["S101"]                       # 测试里允许 assert

[tool.ruff.lint.isort]
known-first-party = ["crawler"]
```

**建议的引入节奏**

1. 先开 `E, F, I` → 修完并提交。
2. 再加 `UP, B, SIM` → 逐批修。
3. 对确实不想改的地方，用 `# noqa: XXXX` **并写明理由**，不要全局放行。

### 8.2 静态类型检查：`mypy` / `pyright`

```bash
uv run mypy src
```

```toml
[tool.mypy]
python_version = "3.11"
strict = true
warn_unreachable = true
plugins = ["pydantic.mypy"]

[[tool.mypy.overrides]]
module = ["parsel.*"]          # 没有类型存根的第三方库
ignore_missing_imports = true
```

**循序渐进策略**

- 新模块一开始就用 `strict`；
- 旧代码先用默认模式，再逐个模块开启严格（`[[tool.mypy.overrides]]` 针对模块设置）；
- 第三方库缺类型存根时：安装 `types-xxx` 包，或临时 `ignore_missing_imports`；
- 对确实无法解决的地方，用 `# type: ignore[错误码]` 并加注释。

**mypy 与 pyright 如何选**：mypy 是传统标准；pyright 速度快、与 VS Code（Pylance）体验一致。可在编辑器用 Pylance、在 CI 用 mypy，两者互补。

### 8.3 pre-commit：提交前自动把关

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0                 # 使用时更新到最新版本
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-toml
      - id: check-added-large-files
      - id: detect-private-key  # 防止误提交私钥

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.5.0                 # 使用时更新到最新版本
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.10.0                # 使用时更新到最新版本
    hooks:
      - id: mypy
        additional_dependencies: [pydantic, pydantic-settings]
        files: ^src/
```

```bash
uv run pre-commit install            # 安装 Git 钩子（每个克隆只需一次）
uv run pre-commit run --all-files    # 对所有文件手动跑一遍
uv run pre-commit autoupdate         # 升级各钩子版本
```

**价值**：把"人要记得做的事"变成"提交时自动做的事"。团队里每个人的提交都符合同一标准。

> 注意：pre-commit 只在本地生效，可被 `--no-verify` 绕过，因此**CI 必须再跑一遍**（第 10 周），这才是真正的"门禁"。

### 8.4 Git 协作工作流

**日常必会命令**

```bash
git status / git diff / git log --oneline --graph --all
git add -p                       # 交互式选择要提交的片段（养成习惯，提交更干净）
git commit -m "feat: ..."
git switch -c feature/xxx        # 新建并切换分支
git restore <file>               # 丢弃工作区修改
git restore --staged <file>      # 取消暂存
git stash / git stash pop        # 临时收起改动
```

**进阶命令**

| 命令 | 用途 |
|---|---|
| `git rebase -i HEAD~5` | 交互式整理最近 5 个提交（合并、改写、重排） |
| `git rebase main` | 把当前分支"接"到最新的 main 之上，保持线性历史 |
| `git cherry-pick <sha>` | 把某个提交单独摘到当前分支 |
| `git reflog` | 找回"丢失"的提交（误 reset 的救命稻草） |
| `git bisect` | 二分查找引入 bug 的提交 |
| `git revert <sha>` | 生成一个"反向提交"来撤销（适用于已推送的历史） |
| `git blame <file>` | 查看每行是谁、哪次提交修改的 |

**`merge` 与 `rebase` 的取舍**

- `merge`：保留分支真实历史，产生合并提交；**公共分支**上使用。
- `rebase`：重写历史，使其线性整洁；**只对自己尚未共享的本地分支**使用。
- **黄金法则**：永远不要 `rebase` 已经推送并被他人使用的公共分支。

**分支策略（小团队 / 个人推荐 GitHub Flow）**

```
main  ────●────●────●────●────   （始终可发布）
           \        /
feature     ●──●──●             （短命分支，通过 Pull Request 合并）
```

1. 从 `main` 切出 `feature/xxx` 或 `fix/xxx` 分支；
2. 小步提交，推送，发起 Pull Request；
3. CI 通过 + 代码审查通过后合并（建议 squash merge 或 rebase merge）；
4. 删除分支。

**提交信息规范：Conventional Commits**

```
<type>(<scope>): <简短描述>

[可选正文：说明"为什么"，而不只是"做了什么"]

[可选脚注：Closes #12]
```

| type | 含义 |
|---|---|
| `feat` | 新功能 |
| `fix` | 修复 bug |
| `refactor` | 重构（不改行为） |
| `test` | 测试相关 |
| `docs` | 文档 |
| `chore` | 构建、依赖、杂项 |
| `ci` | CI 配置 |
| `perf` | 性能优化 |

示例：`fix(fetcher): retry on 429 with exponential backoff`

**好提交的标准**：一个提交只做一件事；能单独回滚；信息说明"为什么"。

**Pull Request 与代码审查**

- PR 要小（建议 < 400 行变更），描述写清楚：背景、改动、如何验证、截图（如有 UI）。
- **自己先审一遍自己的 diff** 再请别人看。
- 审查别人时：针对代码而不是人，提问多于命令，区分"必须改"与"建议"。
- 没有合作者？可以给自己的仓库提 PR 再合并，**练习完整流程**；或给开源项目提文档/小 bug PR。

**版本号与发布**：遵循语义化版本 `MAJOR.MINOR.PATCH`（破坏性变更 / 新功能 / 修复），用 Git tag 标记发布（`v0.1.0`），维护 `CHANGELOG.md`。

### 8.5 日志进阶

阶段 1 学过 `logging` 基础，工程化时关注三点：

```python
import logging
import logging.config
import sys

def setup_logging(level: str = "INFO") -> None:
    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "plain": {"format": "%(asctime)s %(levelname)-7s %(name)s: %(message)s"},
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "stream": sys.stderr,
                "formatter": "plain",
            },
        },
        "root": {"level": level, "handlers": ["console"]},
        "loggers": {
            "httpx": {"level": "WARNING"},      # 压低第三方库的噪音
        },
    })

logger = logging.getLogger(__name__)
```

**工程化要点**

- **只在程序入口配置日志**（`cli.py`），库代码里只 `getLogger(__name__)`。
- **分级使用**：`DEBUG`（排查细节）、`INFO`（关键流程）、`WARNING`（可恢复的异常情况）、`ERROR`（失败）、`CRITICAL`（程序无法继续）。
- **日志里不要放敏感信息**：Cookie、Token、密码；善用 `SecretStr`。
- **携带上下文**：URL、重试次数、耗时，方便定位。
- 需要机器可检索时，了解**结构化日志**（JSON 格式输出）：`structlog`、`python-json-logger`；`loguru` 是另一条更简洁的路线，但在库中仍应使用标准 `logging`。
- 桌面程序：日志写到用户数据目录的文件并滚动（`RotatingFileHandler`），崩溃时便于用户反馈。

### 8.6 调试：断点优先于 print

```python
# 内置断点（Python 3.7+），在需要的位置插入
breakpoint()            # 默认进入 pdb，可通过环境变量 PYTHONBREAKPOINT 切换为其他调试器
```

**`pdb` 常用命令**

| 命令 | 含义 |
|---|---|
| `n` | 执行下一行（不进入函数） |
| `s` | 进入函数 |
| `c` | 继续运行到下一个断点 |
| `r` | 运行到当前函数返回 |
| `l` / `ll` | 显示当前/整个函数的源码 |
| `p expr` / `pp expr` | 打印/美化打印表达式 |
| `w` | 查看调用栈 |
| `u` / `d` | 在调用栈中上移/下移 |
| `b 42` | 在第 42 行设断点 |
| `q` | 退出 |

**事后调试**

```bash
python -m pdb -c continue script.py     # 程序抛异常时自动进入 pdb 现场
pytest --pdb                             # 测试失败时进入调试器
```

**IDE 调试（VS Code / PyCharm）**：必须掌握——条件断点、日志断点（不改代码打印变量）、监视表达式、调用栈、"异常时中断"。

**调试的思路**

1. **稳定复现**：先写出能触发问题的最小用例（最好直接写成测试）。
2. **缩小范围**：二分法——注释一半代码、`git bisect` 定位引入问题的提交。
3. **验证假设**：先猜原因，再用断点/日志证实，而不是乱改。
4. **修复后补测试**：防止回归。

### 8.7 性能分析：先测量，后优化

```bash
python -m cProfile -o out.prof -m crawler run     # 函数级耗时统计
uv run snakeviz out.prof                           # 可视化（需安装 snakeviz）
```

```python
import pstats
p = pstats.Stats("out.prof")
p.sort_stats("cumulative").print_stats(15)
```

| 工具 | 用途 |
|---|---|
| `timeit` | 对小段代码做微基准测试 |
| `cProfile` + `snakeviz` | 找出耗时最多的函数 |
| `py-spy` | 不改代码、不停服务，对运行中的进程采样（生产排查利器） |
| `line_profiler` | 逐行耗时 |
| `tracemalloc` | 内存分配追踪，查内存泄漏 |
| `memray` / `scalene` | 更强大的内存/CPU 分析 |

**铁律**：

1. 先保证**正确**，再谈**性能**。
2. **先分析找到瓶颈**，通常 90% 的时间花在 10% 的代码上。
3. 爬虫的瓶颈大概率是**网络 I/O**，优化解析器收益很小；应优化并发与连接复用——这正是阶段 3 的内容。
4. 优化前后要用同一份数据重复测量，并记录对比。

### 8.8 本周练习

1. **练习 A（必做）**：给项目配置 `ruff`，先跑 `ruff check .` 看有多少问题，分批修复并按类别提交（例如先 `I` 导入排序，再 `UP`，再 `B`）。
2. **练习 B（必做）**：开启 `mypy --strict`，记录错误数，修到 0（允许少量带说明的 `type: ignore`）；统计发现了几个真实潜在 bug。
3. **练习 C（必做）**：配置 `pre-commit`，故意提交一个格式混乱、含未使用导入的文件，观察钩子拦截与自动修复。
4. **练习 D（必做）**：用 `git rebase -i` 把本周凌乱的小提交整理成**逻辑清晰的 5～8 个提交**，信息遵循 Conventional Commits。
5. **练习 E**：制造一个冲突（两个分支改同一行），练习手动解决合并冲突；再用 `git reflog` 找回一次"误删"的提交。
6. **练习 F**：把爬虫中所有 `print` 替换为 `logging`，实现 `--verbose` / `--quiet` 命令行选项来调节日志级别。
7. **练习 G**：用 `cProfile` 分析一次完整的爬取，写出"耗时 Top 5 函数"以及你的优化假设（先不优化，留给阶段 3）。
8. **练习 H**：在 GitHub 上给你的仓库建立一个 Issue → 分支 → PR → 合并的完整流程。

### 8.9 自测题

- `ruff check` 与 `ruff format` 分别做什么？为什么说 pre-commit 之外还要在 CI 里检查？
- mypy 报"缺少类型存根"时有哪几种处理方式？
- `merge`、`rebase`、`squash merge` 的区别？哪种情况绝对不能 `rebase`？
- `git revert` 与 `git reset` 的区别？已推送的错误提交应该用哪个？
- 为什么日志里 `logger.info("x=%s", x)` 优于 `f"x={x}"`？
- 为什么优化前一定要先做性能分析？

### 8.10 阅读

- Ruff 官方文档：Rules 列表（挑选适合自己的规则）
- mypy 官方文档：*Getting started*、*Existing code*
- *Pro Git*（免费在线书）：第 3 章（分支）、第 7 章（高级工具：rebase、reflog、bisect）
- *Conventional Commits* 规范
- Google *Engineering Practices*：Code Review 指南
- Python 官方文档：`pdb`、`cProfile`、`tracemalloc`、`logging` HOWTO / Cookbook

---

## 第 9 周：自动化测试

### 本周目标

- 理解测试的价值与"测试金字塔"
- 熟练使用 `pytest`：断言、fixture、参数化、标记、`monkeypatch`
- 掌握 mock 与测试替身，**让测试不依赖真实网络**
- 为爬虫的解析层、请求层、服务层写出可靠的测试
- 了解覆盖率及其局限，了解 PyQt 程序的测试方式

### 9.1 为什么测试，以及测什么

**测试的价值**：

1. **敢改**：重构、升级依赖时，测试是安全网；
2. **活文档**：测试展示了函数应当怎么用；
3. **倒逼设计**：难以测试的代码，往往是耦合过重的代码；
4. **更快发现问题**：越早发现，修复成本越低。

**测试金字塔**

```
        ▲  少量
       /E2E\        端到端：真实环境，慢、脆弱
      /------\
     /集成测试\      多个模块协作：如 service + 假 fetcher + 真 SQLite
    /----------\
   /  单元测试   \    单个函数/类：快、稳定、数量最多
  /--------------\ ▼  大量
```

**爬虫项目里最值得测试的部分（按性价比排序）**

1. **解析器**（纯函数：HTML → 数据）：最容易测、价值最高。网站改版时，测试第一个告诉你。
2. **数据清洗 / 校验逻辑**：价格、日期、文本规范化。
3. **去重、增量判断、断点续爬逻辑**。
4. **请求层的重试、限速、异常处理**（用模拟响应）。
5. **服务编排**：用假的 fetcher 与内存存储。

**不适合在单元测试里做的事**：直接访问真实网站（慢、不稳定、对对方不友好、结果随时变）。

### 9.2 pytest 基础

```python
# tests/test_parsers.py
import pytest
from crawler.parsers.example_site import parse_price

def test_parse_price_simple():
    assert parse_price("¥99.5") == 99.5

def test_parse_price_with_thousands_separator():
    assert parse_price("¥1,299.00") == 1299.0

def test_parse_price_invalid_raises():
    with pytest.raises(ValueError, match="invalid price"):
        parse_price("面议")
```

```bash
uv run pytest                    # 运行全部
uv run pytest tests/test_parsers.py::test_parse_price_simple   # 单个
uv run pytest -k "price and not invalid"                       # 按名称过滤
uv run pytest -x                 # 遇到第一个失败就停
uv run pytest --lf               # 只重跑上次失败的
uv run pytest -vv                # 详细输出
uv run pytest --pdb              # 失败时进入调试器
```

**约定**：文件名 `test_*.py`；函数名 `test_*`；使用普通 `assert`（pytest 会自动给出详细的断言失败信息）。

**命名建议**：`test_<被测对象>_<场景>_<期望>`，例如 `test_fetch_on_429_retries_then_succeeds`。

**好测试的特征（FIRST）**：Fast（快）、Independent（相互独立）、Repeatable（可重复）、Self-validating（自动判定）、Timely（及时编写）。

**AAA 结构**

```python
def test_dedup_removes_duplicates():
    # Arrange：准备
    items = [{"id": 1}, {"id": 2}, {"id": 1}]
    # Act：执行
    result = dedup(items, key="id")
    # Assert：断言
    assert [i["id"] for i in result] == [1, 2]
```

### 9.3 参数化：一个测试，多组数据

```python
import pytest

@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("¥99", 99.0),
        ("¥1,299.00", 1299.0),
        ("  88.8 元 ", 88.8),
        ("0", 0.0),
    ],
    ids=["simple", "thousands", "with-unit", "zero"],
)
def test_parse_price(raw, expected):
    assert parse_price(raw) == expected

@pytest.mark.parametrize("bad", ["", "面议", "abc", None])
def test_parse_price_bad_input(bad):
    with pytest.raises(ValueError):
        parse_price(bad)
```

**价值**：边界值（空串、None、超长、特殊字符、Unicode）一次覆盖；新增用例只需加一行数据。

### 9.4 Fixture：准备与清理测试环境

```python
# tests/conftest.py   ← 放在这里的 fixture 对整个目录可见
from pathlib import Path
import pytest

FIXTURES = Path(__file__).parent / "fixtures"

@pytest.fixture
def article_html() -> str:
    """读取保存的真实页面样本"""
    return (FIXTURES / "article_page.html").read_text(encoding="utf-8")

@pytest.fixture
def storage(tmp_path):
    """每个测试获得一个全新、独立的临时数据库"""
    from crawler.storage import SqliteStorage
    s = SqliteStorage(tmp_path / "test.db")
    s.init_schema()
    yield s                      # yield 之前是准备，之后是清理
    s.close()
```

```python
def test_parse_article(article_html):
    article = parse_article(article_html)
    assert article.title == "示例标题"
    assert len(article.tags) == 3

def test_save_and_load(storage):
    storage.save(Article(title="a", url="https://x.com/1"))
    assert storage.count() == 1
```

**要点**

- fixture 通过**参数名**自动注入。
- `scope`：`function`（默认，每个测试一次）、`module`、`session`（整个测试会话一次，适合昂贵资源）。
- 内置常用 fixture：

| fixture | 用途 |
|---|---|
| `tmp_path` | 每个测试独立的临时目录（`pathlib.Path`） |
| `monkeypatch` | 临时修改环境变量、属性、字典、工作目录 |
| `capsys` / `capfd` | 捕获标准输出/错误 |
| `caplog` | 捕获日志，断言日志内容 |
| `request` | 访问当前测试上下文 |

**测试 HTML 解析器的最佳实践**：把真实页面保存为 `tests/fixtures/*.html`，解析器测试读取这些**固定样本**。网站改版后，把新页面存为新样本，旧测试告诉你哪些字段失效。

### 9.5 Mock 与测试替身

**测试替身的种类**

| 类型 | 说明 |
|---|---|
| Stub（桩） | 返回预设的固定值 |
| Fake（伪实现） | 简化但可工作的真实实现，如内存存储 |
| Mock（模拟对象） | 可记录调用并断言"是否被调用、参数是什么" |
| Spy（间谍） | 包装真实对象，同时记录调用 |

**`monkeypatch`：替换属性与环境**

```python
def test_settings_read_env(monkeypatch):
    monkeypatch.setenv("CRAWLER_REQUEST_TIMEOUT", "3.5")
    from crawler.settings import Settings
    assert Settings().request_timeout == 3.5

def test_no_sleep(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)   # 测试重试时不真的等待
```

**`unittest.mock`**

```python
from unittest.mock import MagicMock, patch

def test_service_calls_storage():
    fetcher = MagicMock()
    fetcher.fetch.return_value = "<html>...</html>"
    storage = MagicMock()

    service = CrawlService(fetcher, storage)
    service.run(["https://example.com/1"])

    fetcher.fetch.assert_called_once_with("https://example.com/1")
    storage.save.assert_called_once()

# patch 要打在"被使用的位置"，而不是"定义的位置"
with patch("crawler.service.time.sleep"):
    ...
```

**黄金法则：patch 在使用处**。如果 `service.py` 里写了 `from time import sleep`，应 patch `crawler.service.sleep`。

**过度 mock 的陷阱**：mock 太多，测试只是在验证"我的代码调用了我 mock 的东西"，并没有验证行为。优先使用 **Fake**（如内存存储、假 fetcher）：

```python
class FakeFetcher:
    def __init__(self, pages: dict[str, str]):
        self.pages = pages
        self.requested: list[str] = []

    def fetch(self, url: str) -> str:
        self.requested.append(url)
        try:
            return self.pages[url]
        except KeyError:
            raise FetchError(url, 404) from None

def test_service_skips_failed_pages(storage):
    fetcher = FakeFetcher({"u1": "<html>ok</html>"})   # u2 会 404
    result = CrawlService(fetcher, storage).run(["u1", "u2"])
    assert result.succeeded == 1 and result.failed == 1
```

> 这得益于第 4 周与第 7 周的设计：**依赖通过构造函数注入**，测试时才能轻易替换。**能轻松写测试，是好设计的标志。**

**模拟 HTTP 请求**

| 你用的库 | 对应工具 |
|---|---|
| `httpx` | `respx` |
| `requests` | `responses` 或 `requests-mock` |
| `aiohttp` | `aioresponses` |
| 录制/回放真实响应 | `vcrpy`（首次真实请求并保存，之后回放） |

```python
import httpx, respx
import pytest
from crawler.fetcher import Fetcher
from crawler.errors import FetchError

@respx.mock
def test_fetch_retries_on_500_then_succeeds(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    route = respx.get("https://example.com/page").mock(
        side_effect=[
            httpx.Response(500),
            httpx.Response(500),
            httpx.Response(200, text="<html>ok</html>"),
        ]
    )
    html = Fetcher(max_retries=3).fetch("https://example.com/page")
    assert html == "<html>ok</html>"
    assert route.call_count == 3

@respx.mock
def test_fetch_raises_after_max_retries(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    respx.get("https://example.com/page").mock(return_value=httpx.Response(503))
    with pytest.raises(FetchError):
        Fetcher(max_retries=2).fetch("https://example.com/page")
```

**时间相关逻辑**：用 `time-machine` 或 `freezegun` 冻结时间，避免依赖当前日期。

### 9.6 标记与测试分类

```toml
[tool.pytest.ini_options]
markers = [
    "slow: 耗时较长的测试",
    "network: 需要真实网络的测试（默认不在 CI 中运行）",
]
addopts = "-ra --strict-markers -m 'not network'"
```

```python
@pytest.mark.network
def test_real_site_smoke():
    ...

@pytest.mark.skipif(sys.platform == "win32", reason="POSIX only")
def test_symlink(): ...

@pytest.mark.xfail(reason="已知问题 #42", strict=True)
def test_known_bug(): ...
```

```bash
uv run pytest -m network          # 手动跑真实网络的冒烟测试
```

### 9.7 覆盖率

```bash
uv run pytest --cov=crawler --cov-report=term-missing --cov-report=html
# term-missing 会列出未覆盖的行号；htmlcov/index.html 可视化查看
```

```toml
[tool.coverage.run]
branch = true            # 分支覆盖率（比行覆盖率更有意义）
source = ["src/crawler"]

[tool.coverage.report]
fail_under = 80          # 低于阈值时失败（CI 门禁）
exclude_lines = ["pragma: no cover", "if TYPE_CHECKING:", "raise NotImplementedError"]
```

**正确认识覆盖率**

- 覆盖率能告诉你"**哪些代码肯定没被测过**"，但**不能保证测过的代码是对的**（没有有效断言也算覆盖）。
- **不要为了数字而写测试**；核心业务逻辑追求高覆盖，胶水代码、界面代码可以低一些。
- 80% 左右是务实的起点；更值得关注的是"覆盖率趋势"与"关键路径是否被测"。

### 9.8 更多测试技巧（了解）

| 技巧 | 工具 | 说明 |
|---|---|---|
| 属性测试 | `hypothesis` | 自动生成大量随机输入，验证"对任意输入都成立"的性质；擅长发现边界 bug |
| 快照测试 | `syrupy` | 把复杂输出保存为快照，变化时提示审阅 |
| 并行测试 | `pytest-xdist` | `pytest -n auto` 多进程加速 |
| 异步测试 | `pytest-asyncio` / `anyio` | 阶段 3 会用到 |
| 变异测试 | `mutmut` | 检验"测试能否发现被故意改坏的代码" |
| 测试随机顺序 | `pytest-randomly` | 暴露测试之间的隐式依赖 |

```python
from hypothesis import given, strategies as st

@given(st.text())
def test_normalize_is_idempotent(s):
    once = normalize(s)
    assert normalize(once) == once      # 性质：规范化两次与一次结果相同
```

### 9.9 TDD 与修 bug 的正确姿势

**TDD 循环**：红（写一个失败的测试）→ 绿（写最少代码让它通过）→ 重构（保持测试通过的前提下整理代码）。

**不必教条地全程 TDD，但强烈建议在"修 bug"时这样做**：

1. 先写一个能**复现这个 bug 的失败测试**；
2. 修复代码，让测试通过；
3. 这个测试永远留在仓库里，**同样的 bug 不会再次出现**。

### 9.10 PyQt 程序怎么测试

**核心思路：让界面"薄"，把逻辑放在可测试的普通 Python 类里。**

```
View（QWidget，只负责显示和转发用户操作）
  ↓ 信号/调用
Presenter / ViewModel / Service（普通 Python，无需 Qt 即可测试）
  ↓
Model / Storage / Fetcher
```

- 90% 的逻辑测试，**不需要启动 Qt**，用普通 pytest 即可。
- 需要测试界面交互时，使用 `pytest-qt`：

```python
# pip/uv 安装 pytest-qt
from PyQt6.QtCore import Qt

def test_button_click_updates_label(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)                 # 让 qtbot 管理窗口生命周期

    window.input.setText("hello")
    qtbot.mouseClick(window.button, Qt.MouseButton.LeftButton)

    assert window.label.text() == "HELLO"

def test_signal_emitted(qtbot):
    worker = Worker()
    with qtbot.waitSignal(worker.finished, timeout=2000) as blocker:
        worker.start()
    assert blocker.args[0] == "done"
```

- 在无显示器的 CI 里运行：设置环境变量 `QT_QPA_PLATFORM=offscreen`（Linux 上可能还需 `xvfb`）。
- 耗时操作（网络请求）在测试里用假对象替换，避免真的起线程访问网络。

### 9.11 本周练习

1. **练习 A（必做）**：为解析器写测试：保存 3 个以上真实页面作为 `tests/fixtures/`，用参数化覆盖正常页面、字段缺失页面、异常结构页面。
2. **练习 B（必做）**：用 `respx`（或 `responses`）测试请求层：成功、404、500 后重试成功、重试耗尽抛异常、超时。
3. **练习 C（必做）**：写 `FakeFetcher` + 内存/临时 SQLite，测试 `service` 的完整流程（成功、部分失败、重复 URL 去重）。
4. **练习 D（必做）**：配置覆盖率，把核心模块（解析、清洗、去重）提高到 85% 以上，并阅读 HTML 报告，找出"为什么没覆盖"。
5. **练习 E**：故意在解析器里引入一个 bug（比如把某个 CSS 选择器写错），确认测试会失败；再用"先写失败测试、再修复"的方式修复一个真实 bug。
6. **练习 F**：用 `hypothesis` 为一个清洗函数写属性测试（如幂等性、输出不含多余空白）。
7. **练习 G（PyQt 项目）**：把业务逻辑从窗口类中抽出来，为其写不依赖 Qt 的单元测试；再用 `pytest-qt` 写 2 个界面交互测试。
8. **练习 H**：把 `-m 'not network'` 配好，并写一个标记为 `network` 的冒烟测试。

### 9.12 自测题

- 测试金字塔为什么是"下宽上窄"？
- 为什么不能在单元测试里直接请求真实网站？
- `patch("a.b.c")` 应该 patch 在"定义处"还是"使用处"？
- Fixture 的 `yield` 前后分别做什么？`scope` 有什么作用？
- Mock 与 Fake 如何取舍？过度 mock 有什么问题？
- 覆盖率 100% 是否意味着没有 bug？为什么？
- 为什么说"难以测试的代码通常设计有问题"？
- 修 bug 时为什么要先写失败的测试？

### 9.13 阅读

- pytest 官方文档：*Get Started*、*How-to guides*（fixtures、parametrize、monkeypatch）
- 《Python Testing with pytest》（Brian Okken）
- 《Architecture Patterns with Python》第 3、5 章（Fake、依赖注入与测试）
- `respx`、`pytest-qt`、`hypothesis` 官方文档
- Martin Fowler：*Mocks Aren't Stubs*
- 阅读 `httpx` 或 `attrs` 仓库的 `tests/` 目录，观察测试风格与组织方式

---

## 第 10 周：打包、Docker、CI 与综合项目

### 本周目标

- 掌握 Python 包的构建与分发（wheel / sdist），了解发布到 PyPI 的流程
- 掌握桌面程序打包（PyInstaller）与常见坑
- 会写 Dockerfile 与 docker compose
- 用 GitHub Actions 搭建 CI：每次提交自动检查、测试、构建
- 完成阶段综合项目：把旧爬虫项目改造为工程化项目

### 10.1 Python 包的构建与分发

**概念**

| 概念 | 说明 |
|---|---|
| sdist | 源码分发包（`.tar.gz`），安装时需要构建 |
| wheel | 预构建包（`.whl`），安装快，现代标准 |
| PyPI | 官方包索引；TestPyPI 是练习用的沙盒站点 |
| 构建后端 | hatchling / setuptools / flit / uv_build 等，由 `[build-system]` 指定 |

```bash
uv build                               # 生成 dist/*.whl 和 dist/*.tar.gz
pip install dist/crawler_kit-0.1.0-py3-none-any.whl   # 在干净环境里验证安装

# 发布（先在 TestPyPI 练习）
uv publish --publish-url https://test.pypi.org/legacy/ --token <token>
```

**发布前检查清单**

- [ ] 版本号已更新（遵循语义化版本）；
- [ ] `README.md`、`LICENSE`、元数据完整；
- [ ] 在**干净的虚拟环境**里安装 wheel 并运行命令行入口，确认能用；
- [ ] 确认没有把测试数据、密钥打进包里（检查 wheel 内容：`unzip -l dist/*.whl`）；
- [ ] 打 Git tag（`git tag v0.1.0 && git push --tags`）。

**安全发布**：使用 PyPI 的 **Trusted Publishing**（OIDC），在 GitHub Actions 里发布时无需存储长期令牌。

> 不是所有项目都要发布到 PyPI。你的爬虫项目可以**只做到"能构建、能 `pip install` 本地 wheel"**，重点是掌握流程。

### 10.2 桌面程序打包：PyInstaller（PyQt 项目）

```bash
uv add --dev pyinstaller
uv run pyinstaller --name MyApp --windowed --icon assets/app.ico \
    --add-data "assets;assets" src/myapp/__main__.py
#  --windowed：不显示控制台窗口（调试时先去掉它，才能看到报错）
#  --add-data 的分隔符：Windows 用分号 ;，macOS/Linux 用冒号 :
#  默认 onedir（输出一个目录）；--onefile 为单文件（启动时需解压，较慢）
```

**使用 `.spec` 文件精细控制**（首次运行后会生成），可配置隐藏导入、数据文件、排除模块。

**资源路径是最大的坑**：打包后文件不在源码目录里，必须兼容两种运行方式。

```python
import sys
from pathlib import Path

def resource_path(relative: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / relative

icon = resource_path("assets/app.ico")
```

**常见问题与对策**

| 问题 | 对策 |
|---|---|
| 运行报 `ModuleNotFoundError` | 动态导入的模块需用 `--hidden-import` 或在 spec 中声明 |
| 资源文件找不到 | 使用 `resource_path`，并在打包时 `--add-data` |
| 体积巨大 | 使用虚拟环境打包（避免把无关库带进来）；`--exclude-module`；优先 `onedir` |
| 杀毒软件误报 | `onefile` 更易触发；使用代码签名证书、提交误报申诉、改用 `onedir` |
| 启动慢 | `onefile` 每次需解压到临时目录；改用 `onedir` + 安装包 |
| 用户数据写在程序目录 | 配置、日志写入用户数据目录（如 `platformdirs` 库提供的路径），不要写到安装目录 |
| 在别的电脑运行失败 | 在**干净的虚拟机/机器**上测试；Windows 注意 VC++ 运行库 |

**延伸路线（了解）**

- **Nuitka**：把 Python 编译为 C 再编译成机器码，启动与运行性能较好、一定程度上更难反编译；
- **安装包制作**：Windows 用 Inno Setup / NSIS，macOS 做 `.dmg` 并签名公证；
- **自动更新**：检查版本接口 + 下载新包 + 重启替换（可用 `PyUpdater` 一类方案，或自行实现简单流程）；
- **PySide6** 提供官方的 `pyside6-deploy`；
- **签名**：Windows 代码签名证书可减少"未知发布者"提示。

> 提示：`PyInstaller` 对不同操作系统是**各自构建**的，Windows 的包要在 Windows 上打（可借助 CI 的 Windows runner 自动打）。

### 10.3 Docker：可复现的运行环境

**核心概念**

| 概念 | 类比 |
|---|---|
| 镜像（Image） | 只读的"安装包/模板"，由 Dockerfile 构建 |
| 容器（Container） | 镜像的运行实例 |
| 卷（Volume） | 容器外持久化数据的位置 |
| 仓库（Registry） | 存放镜像的地方，如 Docker Hub、GHCR |

**Dockerfile（使用 uv 的多阶段构建示例）**

```dockerfile
# ---------- 构建阶段 ----------
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# 先只复制依赖声明，利用 Docker 层缓存：依赖不变就不用重新安装
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# 再复制源码并安装项目本身
COPY src ./src
COPY README.md ./
RUN uv sync --frozen --no-dev

# ---------- 运行阶段 ----------
FROM python:3.12-slim

RUN useradd --create-home --uid 1000 appuser
WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER appuser
ENTRYPOINT ["crawler"]
CMD ["--help"]
```

**`.dockerignore`（和 `.gitignore` 同样重要）**

```
.git
.venv
__pycache__
*.pyc
.mypy_cache
.ruff_cache
.pytest_cache
htmlcov
tests
.env
data
```

**构建与运行**

```bash
docker build -t crawler-kit:0.1.0 .
docker run --rm --env-file .env -v "$(pwd)/data:/app/data" crawler-kit:0.1.0 run --help
docker image ls
docker logs <container>
docker exec -it <container> sh
```

**最佳实践**

1. **利用层缓存**：变化少的步骤（装依赖）放前面，变化多的（拷贝源码）放后面。
2. **多阶段构建**：构建工具不进入最终镜像，减小体积与攻击面。
3. **不用 root 运行**：创建普通用户。
4. **不在镜像里放密钥**：通过环境变量或 secrets 注入；镜像层里的东西可以被查看。
5. **固定基础镜像版本**，不要无脑用 `latest`。
6. **一个容器一个进程**，日志输出到标准输出。
7. 需要浏览器（Playwright）时，使用官方提供的带浏览器依赖的基础镜像。

**docker compose：应用 + 数据库**

```yaml
# compose.yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: crawler
      POSTGRES_PASSWORD: ${DB_PASSWORD:?请在 .env 中设置 DB_PASSWORD}
      POSTGRES_DB: crawler
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U crawler"]
      interval: 5s
      timeout: 3s
      retries: 10

  app:
    build: .
    depends_on:
      db:
        condition: service_healthy
    environment:
      CRAWLER_DB_URL: postgresql://crawler:${DB_PASSWORD}@db:5432/crawler
    volumes:
      - ./data:/app/data

volumes:
  pgdata:
```

```bash
docker compose up -d --build
docker compose logs -f app
docker compose down            # 停止并移除容器（加 -v 会连数据卷一起删，谨慎！）
```

> 本周先熟悉概念并跑通"应用 + 数据库"；阶段 4 会在此基础上加入 PostgreSQL、Redis 与 FastAPI。

### 10.4 持续集成：GitHub Actions

**CI 的目标**：每次推送或发起 PR，在干净环境里**自动**执行格式检查、静态分析、测试，失败则不允许合并。**这是 pre-commit 之外的真正门禁。**

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5          # 版本号请以官方最新为准
        with:
          enable-cache: true
      - run: uv python install 3.12
      - run: uv sync --frozen
      - run: uv run ruff check .
      - run: uv run ruff format --check .
      - run: uv run mypy src

  test:
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, windows-latest]
        python: ["3.11", "3.12", "3.13"]
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
        with:
          enable-cache: true
      - run: uv python install ${{ matrix.python }}
      - run: uv sync --frozen
      - run: uv run pytest --cov=crawler --cov-report=xml
      - uses: actions/upload-artifact@v4
        if: matrix.os == 'ubuntu-latest' && matrix.python == '3.12'
        with:
          name: coverage
          path: coverage.xml

  build:
    needs: [quality, test]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv build
      - uses: actions/upload-artifact@v4
        with:
          name: dist
          path: dist/
```

**理解关键点**

- `on`：触发条件；`jobs`：并行执行的任务；`steps`：任务内按顺序执行的步骤；
- `matrix`：同一任务在多个系统/版本组合上并行运行；
- `needs`：任务依赖，保证先通过检查再构建；
- `actions/*`、`astral-sh/*`：可复用的社区动作，**固定到具体版本**（或提交哈希）更安全；
- **Secrets**：在仓库设置中配置，通过 `${{ secrets.NAME }}` 引用，不要明文写进工作流。

**让 CI 真正起作用**：在仓库的 *Branch protection rules* 中把 `main` 设为必须通过 CI 检查、必须经过 PR 才能合并。

**进阶（了解）**

- **缓存**：缓存依赖目录加速构建；
- **定时任务**：`schedule: - cron: "0 3 * * 1"` 每周跑一次依赖更新或真实网络冒烟测试（用于发现网站改版）；
- **发布工作流**：推送 `v*` tag 时自动构建、创建 GitHub Release、（使用 Trusted Publishing）发布到 PyPI；
- **PyInstaller 自动打包**：在 `windows-latest` runner 上构建 `.exe` 并上传为发布附件；
- **构建并推送 Docker 镜像**到 GHCR；
- **徽章**：在 README 顶部展示 CI 状态、覆盖率、版本徽章；
- 其他 CI 平台思想相同：GitLab CI、Gitea Actions、Jenkins。

### 10.5 综合项目：爬虫项目工程化改造

这是**本阶段的毕业作业**，对应阶段 2 的全部内容。

**起点**：你原来的爬虫项目（一堆脚本、硬编码、无测试）。
**终点**：一个陌生人 clone 后能一键运行、有测试保障、有自动化质量门禁的规范项目。

**需求清单**

| 周次 | 工作项 |
|---|---|
| 第 7 周 | `src/` 布局；`pyproject.toml`；`uv.lock`；`Settings`（pydantic-settings）；`.env.example`；README |
| 第 8 周 | `ruff`、`mypy --strict` 全部通过；`pre-commit`；`logging` 替换 `print`；整理 Git 历史为清晰的提交；Issue/PR 流程 |
| 第 9 周 | 解析器、清洗、去重、请求层、服务层的测试；覆盖率 ≥ 80%；`network` 标记的冒烟测试 |
| 第 10 周 | 能 `uv build`；Dockerfile + compose；GitHub Actions（质量 + 多版本测试 + 构建）；打 `v0.1.0` tag |

**分步骤的改造路线（建议按顺序，每步一个/多个提交）**

```
1. 建仓库，写 .gitignore，把旧代码原样提交为基线（保留"改造前"的历史）
2. 迁移到 src 布局 + pyproject.toml + uv，确保行为不变
3. 抽离配置 → Settings；清除硬编码与密钥
4. 分层拆分：fetcher / parsers / storage / service / cli
5. 引入 ruff（先 E,F,I），修复，提交；再逐步加规则
6. 引入 mypy，补全类型注解，修复，提交
7. 引入 pre-commit
8. 先为解析器写测试（风险最低、价值最高），再写 fetcher / service 测试
9. 在测试保护下做重构（改善命名、消除重复、拆分长函数）
10. 配置覆盖率与门槛
11. 写 Dockerfile / compose
12. 写 GitHub Actions；开启分支保护
13. 完善 README、CHANGELOG，打 tag，构建发布产物
```

**交付物**

- [ ] 公开的 GitHub 仓库，包含清晰的提交历史与至少 3 个已合并的 PR
- [ ] `uv sync && uv run pytest` 在干净环境一次通过
- [ ] CI 绿灯，README 顶部有 CI 徽章
- [ ] `docker compose up` 可运行
- [ ] README 含：简介、安装、配置表、使用示例、架构图、开发指南
- [ ] `docs/` 或 README 中有一段"**改造前后对比**"：代码行数、测试数、覆盖率、可维护性的变化，以及你的收获与遗留问题

**可选加分项**

- [ ] 加入 `Makefile` / `justfile` / `taskipy`，统一常用命令（`make test`、`make lint`）
- [ ] 加入 `CONTRIBUTING.md` 与 Issue/PR 模板
- [ ] Dependabot / Renovate 自动更新依赖
- [ ] 在 CI 中增加 `pip-audit` 安全扫描
- [ ] 用 `mkdocs-material` 生成文档站点
- [ ] 为 PyQt 项目（若有）在 CI 中构建 Windows 安装包

### 10.6 本周练习

1. **练习 A（必做）**：`uv build` 构建 wheel，在**全新虚拟环境**里安装并运行 `crawler --help`；用 `unzip -l` 检查包内容。
2. **练习 B（必做）**：编写 Dockerfile，镜像构建成功并能运行命令；对比"多阶段/单阶段"、"调整指令顺序前后"的构建时间与镜像体积。
3. **练习 C（必做）**：写 GitHub Actions 工作流，让一个故意破坏格式/类型/测试的 PR 被 CI 拦下，再修复变绿。
4. **练习 D（必做）**：完成综合项目的全部交付物。
5. **练习 E（PyQt 项目）**：用 PyInstaller 打包你的桌面程序，在**另一台干净电脑/虚拟机**上运行，记录遇到的问题与解决办法。
6. **练习 F**：为仓库配置分支保护，并实际体验"CI 不过无法合并"。
7. **练习 G**：写发布工作流：推送 `v*` tag 后自动构建并把 wheel 附到 GitHub Release。
8. **练习 H**：写一篇 800 字以上的博客/README 章节：《把一个爬虫脚本改造成工程化项目的 13 步》。

### 10.7 自测题

- wheel 与 sdist 的区别？为什么要在干净环境里验证安装？
- PyInstaller 打包后资源文件找不到，原因与解决办法是什么？
- Dockerfile 中为什么先复制依赖文件、安装后再复制源码？
- 为什么需要 `.dockerignore`？镜像里为什么不能放密钥？
- pre-commit 与 CI 各自的角色？为什么两者都需要？
- 分支保护要解决什么问题？
- 如果让你向同事介绍这个项目，你会用哪三条命令完成"安装、检查、运行"？

### 10.8 阅读

- Docker 官方文档：*Best practices for writing Dockerfiles*、*Multi-stage builds*、Compose 文档
- GitHub Actions 官方文档：*Workflow syntax*、*Using secrets*、*Security hardening*
- PyInstaller 官方文档：*When things go wrong*（排错必读）、*Using Spec Files*
- Python Packaging User Guide：*Packaging Python Projects*、*Trusted Publishing*
- 阅读 `ruff`、`httpx`、`pytest` 的 `.github/workflows/`，学习成熟项目的 CI 设计

---

## 阶段验收清单

完成 4 周后，逐项自检。

### 概念理解

- [ ] 能解释虚拟环境、依赖声明与锁定、`pyproject.toml` 各段的作用
- [ ] 能说明 `src/` 布局与分层架构的理由及依赖方向
- [ ] 能解释 `merge` / `rebase` / `revert` / `reset` 的区别与适用场景
- [ ] 能说明测试金字塔、Fake 与 Mock 的区别、覆盖率的价值与局限
- [ ] 能解释 wheel 与 sdist、镜像与容器、pre-commit 与 CI 的关系

### 工程实践

- [ ] 项目可通过 `uv sync` 一条命令复现环境
- [ ] 配置与密钥不在代码和 Git 历史中
- [ ] `ruff`、`mypy --strict`、`pytest` 在本地与 CI 都能通过
- [ ] 核心逻辑覆盖率 ≥ 80%，测试不依赖真实网络
- [ ] Git 历史清晰，提交信息规范，用过 PR 流程
- [ ] 能构建 wheel、构建 Docker 镜像、（桌面项目）打出可运行的安装包
- [ ] CI 自动化质量检查，主分支有保护规则

### 小测：口头回答（每题 1～2 分钟）

1. 新同事拿到你的项目，如何在 5 分钟内跑起来？
2. 你如何保证改一处代码不会破坏其他功能？
3. 网站改版导致解析失败，你的项目如何第一时间发现？
4. 提交前有哪些环节在自动帮你把关？为什么 CI 里还要再跑？
5. 密钥不小心提交了，你的处理步骤是什么？
6. 如何让别人不装 Python 也能运行你的程序？（Docker / PyInstaller）

---

## 常见误区与建议

| 误区 | 建议 |
|---|---|
| 一次引入所有工具，被几百条报错劝退 | 逐个引入，分批修复，每步提交 |
| 为了覆盖率数字写没有断言的测试 | 先测核心逻辑与边界；用修 bug 驱动补测试 |
| 测试依赖真实网络、随机数、当前时间 | 全部隔离：Fake、固定样本、冻结时间 |
| mock 一切，测试变成"复述实现" | 优先 Fake 与行为断言，只在边界处 mock |
| 把 `.env`、数据库文件、虚拟环境提交进仓库 | 先写好 `.gitignore`，再 `git add` |
| 提交信息写 "update"、"fix bug"、"123" | 遵循规范，写"为什么" |
| 一个巨大的提交/PR | 小步提交，每个提交只做一件事 |
| Docker 里用 root、用 `latest`、把密钥打进镜像 | 非 root、固定版本、运行时注入 |
| 只在本地跑检查，没有 CI | CI 才是真正的门禁，并设置分支保护 |
| 过度工程化：小脚本也上全套 | 按项目规模取舍：一次性脚本不需要，**会长期维护、会给别人用**的项目才需要 |
| 把重构和新功能混在同一个提交 | 重构在测试保护下单独提交，行为不变 |

### 每周复盘模板

```markdown
## Week N 复盘
- 本周完成的改造项：
- 改造前 → 改造后的可量化对比（错误数、测试数、覆盖率、启动步骤数）：
- 工具报出的最有价值的 3 个问题：
- 遇到的坑与解决办法：
- 仍然模糊的概念：
- 下周计划：
```

---

## 资源汇总

### 书籍

| 书名 | 用途 |
|---|---|
| 《Architecture Patterns with Python》 | 分层、依赖注入、可测试的设计，**本阶段最推荐** |
| 《Python Testing with pytest》 | pytest 系统教程 |
| 《Test-Driven Development with Python》 | 以实战项目讲 TDD（偏 Web，可选读） |
| *Pro Git*（免费在线） | Git 权威参考 |
| 《Docker 实战 / Docker Deep Dive》 | 容器入门到进阶 |
| 《Clean Code》/《重构（第 2 版）》 | 代码整洁与重构手法，思想通用 |

### 官方文档与网站

- [Python Packaging User Guide](https://packaging.python.org/)
- [uv 文档](https://docs.astral.sh/uv/) 与 [Ruff 文档](https://docs.astral.sh/ruff/)
- [mypy 文档](https://mypy.readthedocs.io/) / [pyright 文档](https://microsoft.github.io/pyright/)
- [pytest 文档](https://docs.pytest.org/)
- [pre-commit 文档](https://pre-commit.com/)
- [GitHub Actions 文档](https://docs.github.com/actions)
- [Docker 文档](https://docs.docker.com/)
- [The Twelve-Factor App](https://12factor.net/zh_cn/)
- [Conventional Commits](https://www.conventionalcommits.org/zh-hans/)
- [语义化版本](https://semver.org/lang/zh-CN/)
- [Keep a Changelog](https://keepachangelog.com/zh-CN/)

### 值得对照学习的开源项目配置

| 项目 | 看什么 |
|---|---|
| `httpx` | `pyproject.toml`、测试组织、CI |
| `pydantic` | 类型、工具链配置、文档 |
| `ruff` / `uv` | 工程化的"天花板"，了解即可 |
| `attrs` | 多版本测试矩阵、发布流程 |
| `rich` / `typer` | 小而美的项目结构与 README |

### 视频与演讲

- PyCon / EuroPython 中关于 *Packaging*、*Testing*、*Type Checking in Practice* 的演讲
- Hynek Schlawack 的文章与演讲（Python 打包、测试与 Docker 实践）
- Brian Okken 的 *Test & Code* 播客

---

> **下一步**：完成本阶段验收后进入「阶段 3：并发与异步」。你在本阶段改造出的工程化爬虫项目，将作为阶段 3 的实验对象：把同步的 `fetcher` 改写为异步版本，在**测试和 CI 的保护下**安全地对比性能，并为 PyQt 项目解决界面卡顿问题。有了测试与 CI，这类"改动大、风险高"的重构才有底气。
