# 自动合并规则列表项目

本项目旨在自动从多个来源下载规则列表，并为每个源文件生成独立的格式化规则文件，适用于 Clash 等代理工具。

## 功能

* 从 `sources/` 目录下的多个文本文件中读取规则列表的 URL。
* 为每个源文件独立下载和处理 URL 指向的规则内容。
* 对规则进行自动分类（DOMAIN、DOMAIN-SUFFIX、IP-CIDR 等）。
* 去除重复的规则和注释行（以 `#`, `!`, `/`, `;`, `[` 开头的行）。
* 为每个源文件生成对应的规则列表文件到 `output/` 目录（例如 `sources/telegram.txt` 生成 `output/telegram.list`）。
* 使用 GitHub Actions 自动化此过程，可定时（每天 UTC 0点）或在推送到 `main` 分支时触发。

## 文件结构

```plaintext
.
├── .github/
│   └── workflows/
│       └── merge_rules.yml  # GitHub Actions 工作流程定义
├── sources/
│   ├── twitter.txt        # 存放 Twitter 相关规则列表 URL
│   ├── ai.txt             # 存放 AI 相关规则列表 URL
│   ├── telegram.txt       # 存放 Telegram 相关规则列表 URL
│   ├── youtube.txt        # 存放 YouTube 相关规则列表 URL
│   └── others.txt         # 存放其他规则列表 URL
├── output/
│   ├── twitter.list       # 自动生成的 Twitter 规则列表
│   ├── ai.list            # 自动生成的 AI 规则列表
│   ├── telegram.list      # 自动生成的 Telegram 规则列表
│   ├── youtube.list       # 自动生成的 YouTube 规则列表
│   └── others.list        # 自动生成的其他规则列表
├── .gitignore             # 指定 Git 忽略的文件
├── merge_rules.py         # 执行合并和分类逻辑的 Python 脚本
├── requirements.txt       # Python 依赖库列表 (requests)
└── README.md              # 项目说明文件
```

## 使用方法

1. **克隆仓库**:
   ```bash
   git clone https://github.com/Jacky-Bruse/Clash_Rules.git
   cd Clash_Rules
   ```

2. **添加/修改规则源**:
   * 导航到 `sources/` 目录。
   * 打开现有的 `.txt` 文件或创建新的 `.txt` 文件（文件名将决定输出的规则文件名）。
   * 在文件中添加或删除规则列表的 URL，确保每个有效的 URL 独占一行。
   * 以 `#` 开头的行将被视为注释，会被忽略。

3. **提交更改**:
   ```bash
   git add sources/
   git commit -m "更新规则源列表"
   git push origin main
   ```

4. **自动化处理**:
   * 当你将更改推送到 `main` 分支后，GitHub Actions 会自动触发执行脚本。
   * 或者，Actions 也会按照预定计划（每天 UTC 0 点）自动运行。
   * 如果脚本成功生成了新的规则文件，Actions 会自动将更新后的文件提交回仓库。

5. **手动运行**:
   * 你也可以在 GitHub 仓库页面的 "Actions" 标签页找到 "Merge Rule Lists" 工作流，并手动触发它。

## 获取生成的规则列表

所有生成的规则列表位于仓库的 `output/` 目录中，每个源文件都有对应的 `.list` 文件。

你可以通过以下 URL 格式直接访问最新版本的规则文件（以 telegram.list 为例）:

```
https://raw.githubusercontent.com/Jacky-Bruse/Clash_Rules/main/output/telegram.list
```

## 规则文件格式

生成的规则文件符合标准的 Clash 规则格式，包含以下内容：

```
# NAME: Telegram
# AUTHOR: Jacky-Bruse
# REPO: https://github.com/Jacky-Bruse/Clash_Rules
# UPDATED: 2023-04-23 12:34:56
# DOMAIN: 10
# DOMAIN-SUFFIX: 20
# IP-CIDR: 30
# TOTAL: 60

DOMAIN,telegram.org
DOMAIN,api.telegram.org
DOMAIN-SUFFIX,t.me
DOMAIN-SUFFIX,tdesktop.com
IP-CIDR,91.108.4.0/24
IP-CIDR,91.108.8.0/24
```

## 本地测试

如果你想在本地运行脚本进行测试：

1. 确保你的系统安装了 Python 3 (建议 3.7+)。
2. 创建并激活虚拟环境:
   ```bash
   python -m venv venv
   # Windows
   .\venv\Scripts\activate
   # macOS/Linux
   source venv/bin/activate
   ```
3. 安装依赖:
   ```bash
   pip install -r requirements.txt
   ```
4. 运行脚本:
   ```bash
   python merge_rules.py
   ```
5. 检查 `output/` 目录下生成的规则文件。

## 注意事项

* 添加到源文件中的 URL 应该是可公开访问的，并且指向纯文本格式的规则列表。
* 脚本会自动对规则进行分类，支持的类型包括：DOMAIN, DOMAIN-SUFFIX, DOMAIN-KEYWORD, IP-CIDR, IP-CIDR6, PROCESS-NAME。
* 如果源规则已经带有类型前缀（如 "DOMAIN:"），脚本会保留该分类；否则，会根据规则的模式自动判断类型。
* 每个源文件生成的规则列表是相互独立的，方便用户选择性地使用所需的规则集。 