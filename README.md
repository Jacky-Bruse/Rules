# 自动合并规则列表项目

本项目旨在自动合并来自多个来源的规则列表，并进行去重处理，生成一个统一的规则文件。

## 功能

*   从 `sources/` 目录下的多个文本文件中读取规则列表的 URL。
*   下载每个 URL 指向的规则文件内容。
*   合并所有规则。
*   去除重复的规则和注释行（以 `#`, `!`, `/`, `;`, `[` 开头的行）。
*   将最终合并和去重后的规则列表写入 `dist/merged_rules.list` 文件。
*   使用 GitHub Actions 自动化此过程，可定时（每天 UTC 0点）或在 `sources/` 目录下的文件更新并推送到 `main` 分支时触发。

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
├── dist/
│   └── merged_rules.list  # 自动生成的合并后的规则列表
├── .gitignore             # 指定 Git 忽略的文件
├── merge_rules.py         # 执行合并和去重逻辑的 Python 脚本
├── requirements.txt       # Python 依赖库列表 (requests)
└── README.md              # 项目说明文件
```

## 使用方法

1.  **克隆仓库** (如果你还没有):
    ```bash
    # 用你的仓库 URL 替换下面的地址
    git clone https://github.com/YourUsername/YourRepoName.git
    cd YourRepoName
    ```

2.  **添加/修改规则源**:
    *   导航到 `sources/` 目录。
    *   打开对应的 `.txt` 文件 (例如 `sources/twitter.txt`)。
    *   在文件中添加或删除规则列表的 URL，确保每个有效的 URL 独占一行。
    *   以 `#` 开头的行将被视为注释，会被忽略。

3.  **提交更改**:
    *   将你对 `sources/` 目录下文件的修改添加到 Git:
        ```bash
        git add sources/
        ```
    *   提交这些更改:
        ```bash
        git commit -m "更新规则源列表"
        ```
    *   将更改推送到 GitHub 上的 `main` 分支:
        ```bash
        git push origin main
        ```

4.  **自动化处理**:
    *   当你将更改推送到 `main` 分支后，`.github/workflows/merge_rules.yml` 中定义的 GitHub Action 会自动触发。
    *   或者，该 Action 也会按照预定计划（每天 UTC 0 点）自动运行。
    *   Action 会执行 `merge_rules.py` 脚本。
    *   如果脚本成功生成了新的 `dist/merged_rules.list` 文件（或者更新了现有文件），Action 会自动将这个更新后的文件提交回你的仓库。

5.  **手动运行 (可选)**:
    *   你也可以在 GitHub 仓库页面的 "Actions" 标签页找到 "Merge Rule Lists" 工作流，并手动触发它。

## 获取合并后的列表

合并后的规则列表始终位于仓库的 `dist/merged_rules.list` 文件中。

你可以通过以下 URL 直接访问最新版本的原始文件内容 (请将 `YourUsername` 和 `YourRepoName` 替换为你的 GitHub 用户名和仓库名):

```
https://raw.githubusercontent.com/YourUsername/YourRepoName/main/dist/merged_rules.list
```

## 本地测试 (可选)

如果你想在本地运行脚本进行测试：

1.  确保你的系统安装了 Python 3 (建议 3.7+)。
2.  创建并激活一个虚拟环境 (推荐):
    ```bash
    python -m venv venv
    # Windows
    .\venv\Scripts\activate
    # macOS/Linux
    source venv/bin/activate
    ```
3.  安装依赖:
    ```bash
    pip install -r requirements.txt
    ```
4.  运行脚本:
    ```bash
    python merge_rules.py
    ```
5.  检查 `dist/` 目录下生成的 `merged_rules.list` 文件。
6.  完成后退出虚拟环境:
    ```bash
    deactivate
    ```

## 注意事项

*   添加到源文件中的 URL 应该是可公开访问的，并且指向纯文本格式的规则列表。
*   脚本的网络请求包含基本的超时 (15 秒) 和重试 (最多 3 次) 逻辑。
*   脚本会尝试过滤掉一些明显无效的规则行（例如，不包含 `.` 或 `:` 的行），但这只是基础检查。 