# Beyond Compare Lite - PyQt5

一个类似 Beyond Compare 的简化版文件/文件夹差异比较与合并工具。

## 功能

- 左右两个文件系统面板，支持选择本地文件或文件夹。
- 点击 **Compare** 后，以树形结构显示差异：
  - Only left：只存在于左侧
  - Only right：只存在于右侧
  - Content different：两侧文件内容不同
  - Type mismatch：同名路径一侧是文件，另一侧是文件夹
- 双击文本文件差异，在新窗口中并排显示左右文本内容。
- 使用 `difflib.SequenceMatcher` 进行行级差异计算。
- 使用 `QTextEdit + DiffHighlighter` 高亮差异行。
- 支持同步操作：
  - Copy left -> right
  - Copy right -> left
  - Delete left / Delete right
  - Rename left / Rename right
- 文本合并：在右侧编辑器选择某些行，点击 `Merge selected right lines -> left cursor`，即可插入到左侧光标位置，然后保存左侧文件。

## 环境要求

- Python 3.8+
- PyQt5

安装依赖：

```bash
pip install -r requirements.txt
```

启动：

```bash
python main.py
```

Windows 用户也可以双击：

```text
run.bat
```

Linux/macOS：

```bash
./run.sh
```

## 工程结构

```text
pyqt_beyond_compare_lite/
├─ main.py
├─ requirements.txt
├─ run.bat
├─ run.sh
├─ README.md
└─ app/
   ├─ __init__.py
   ├─ models.py
   ├─ utils.py
   ├─ diff_engine.py
   ├─ diff_thread.py
   ├─ highlighter.py
   ├─ fs_panel.py
   ├─ compare_window.py
   └─ main_window.py
```

## 主要类说明

- `DiffThread`：后台比较线程，避免大文件夹扫描时界面卡死。
- `DiffHighlighter`：基于 `QSyntaxHighlighter` 的文本差异行高亮器。
- `TextCompareWindow`：双栏文本差异与简单合并窗口。
- `FileSystemPanel`：基于 `QFileSystemModel` 的左右文件系统面板。
- `MainWindow`：主界面，负责路径选择、差异树展示和同步操作。

## v2改进说明，继续改了一版，主要改动如下：
- 点击【比较】后，如果发现可打开的文本差异，会自动弹出【查看差异 / 文本合并】窗口，不再必须先到下面列表里双击。
- 差异弹窗改成独立窗口，带系统关闭按钮，同时工具栏增加【关闭窗口】按钮，可正常拖拽移动。
- 页面主要英文按钮、菜单、提示、状态文字已改成中文。
- 左右两侧选择区域支持直接拖拽文件或文件夹进去，包括路径输入框和树形区域。
- 复制、删除、重命名后会自动刷新比较结果，但不会再次强制弹出差异窗口，避免操作时被频繁打断。

## 注意事项

1. 删除、复制、重命名是真实文件操作，请先用测试目录验证。
2. 文本合并是基础行级合并：将右侧选中行插入左侧光标处，不做复杂三方合并。
3. 二进制文件只支持判断是否不同，不支持打开文本差异窗口。
4. 文件夹差异扫描使用递归遍历；界面文件系统浏览使用 `QFileSystemModel`。
