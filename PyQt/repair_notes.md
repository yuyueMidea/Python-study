# mbt_monitor.py 修复记录（TV2.8 20250310）

输入：损坏文本 `mbt_monitor.py`（2964 行，CRLF，每行尾带空格）  
输出：`mbt_monitor_repaired.py`（约 6200 行，LF，`py_compile` 通过，pyflakes 无未定义名称）

> 结论先行：**语法结构已完整还原并可编译；但“语法能过”不等于“逻辑与原版一致”。** 约 140 个被压成一行的方法，其 if/for/try 嵌套深度是启发式推断，必须对照原版或做回归测试。

## 一、确定性修改（无歧义）
1. 去掉 `\r` 和每行行尾空格，统一为 LF。
2. 把压在一行里的多条语句按关键字、括号深度、`:` 拆成多行，并保留语句内部原有空格。
3. 第 2191–2276 行共约 86 个顶格 `def` 缩进进 `MultiTabMonitor` 类。
4. 行内被折叠的多条 `#` 注释拆成独立注释行；注释与后续代码粘连处（如 `# macOS subprocess…`、`#去除头一行的name for …`、`# 写入多个值…为8 self.writeRegVal…` 等十余处）手工指定了断点。
5. 第 2964 行（9128 字符的 OTA 弹框布局，位于 `__main__`）拆成逐条语句，顶层缩进 4 格。
6. 合并在同一行里的第二个方法（如 `setChannelResetClicked` 后面的 `channelItemClick`）拆为独立方法。
7. 日志初始化：`logging.basicConfig` 与 `logger = ...` 移回模块级（它们并不在 `if not os.path.exists('./exportlog')` 里）。**此前分析中“logger 只在 if 里定义”的说法是缩进塌陷造成的误判，现已更正。** 同理，`setGroupAddrList` 中 `loopOneRead()` 在 for 内、`toggleLangTrigger` 的 else 嵌套等“疑似 bug”也属塌陷假象，已还原。

## 二、缩进漂移修复（有较高把握）
| 位置 | 修改 |
|---|---|
| `initMenuList` | `triggered.connect / addAction` 等移出 `if`，回到 for 循环体（样式菜单、语言菜单各一处） |
| `toggleLangTrigger` | for 之后的全部语句回退到方法层 |
| `loadParameter` | 每个 sheet 的汇总逻辑回到 sheet 循环层；重复名检查、`fileNameList` 重建等放到所有 sheet 之后【推断】 |
| `initTabNodeList` | 创建 tab 的部分回到每个 tab 的循环内；末尾 `setCentralWidget` 等回到循环后。QSS 三引号字符串内部未改动 |
| `setGroupAddrList` | for 之后的语句回到循环外 |
| `Com_Receive_Data` | 重新理顺嵌套；`else`（读失败 0x83 分支）挂到 `len % edgeNumber == 0` 的 else 上【推断】 |
| `reloopOneRead`、`updateRenderData`、`loadChannelList`、`updateNodeData`、`settingConfirmEvent`、`keyupSearchText`、`setChannelResetClicked` | 手工逐行调整层级（脚本 relevel 表） |

## 三、推断/重建（请对照原版）
- `mouseMoved`、`toggle_Cursor2`、`removeCursorLine2`、`createCursorLine2`、`monitorMouseMoved`、`switchCursor`、`removeFixedItems`、`createFixedItems`、`handle_sig_dragged_xa/xb`、`setTableItemValue`：原文被 HTML 吞噬（`<` 之后到下一个 `>` 的文字丢失，残留为小写碎片）。已按残片及相邻函数结构重建，其中字体高度 `pheihgt`、XA/XB 线样式、控件名 `input_XA_XB` 的大小写、`switchCursor` 的参数名均为猜测。
- `Com_Receive_Data` 第一处 `Data= byteData.decode('utf-8'," errors="ignore")"` 修为 `errors='ignore'`。
- `updateRenderData` 里 `if 0<=rowLine= len(self.regItemList):` 被吞噬，改为 `if self.loopReadIndex >= len(self.regItemList):`【推断，语义最接近】。
- `initTabNodeList` 约 874–898 行：BUTTONS 对齐代码和 SELECT/SWITCHS 分支开头丢失，按残片 `max_text_len … selectOptionsMap[…] = itemObj` 重建 `itemObj / max_text_len` 循环；BUTTONS 分支其余部分留空。
- `updateLogprogress`：整体丢失，仅据残片重建了判定条件与 `delayRenderFileList/Info/Detail/Finish` 四个分支。
- 某些行尾注释（如 `continue #把下拉选的值转为map方便查找`）原本是**下一行**的注释，损坏时被并到上一行，未移动。

## 四、无法确认（按你的要求不再追查）
- `updateOTAprogress`：整体丢失，仅留 `pass` 桩（OTA 升级进度/应答处理需要补）。
- `updateWriteprogress` 后半段（循环写入时发送下一行）：仅留 `pass` 和说明注释。
- BUTTONS 补空节点的 while 循环（已被注释掉的部分）细节。
- 被吞噬区域里可能还丢失了与上述函数相邻的其他代码，无从得知。

## 五、仍需人工核对的风险点
1. 所有由“单行压缩”还原的方法（`throwErrHandler` 起至 `__main__` 前，约 140 个）：嵌套为启发式。规则是：`return/break/continue` 后退出一层；for/with 体在遇到与循环变量无关的语句后结束；`if self.toggle_text.isChecked():` 只保留日志相关语句。典型风险：多个连续的 `if` 被嵌套成同一层；写文件逻辑是否在 `with` 内。
2. 建议用原版运行时的串口收发日志做回归：重点测 `Com_Receive_Data`、`updateNodeData`、`reloopOneRead`、`saveLoopDataFile`、`parseAndSaveLog`/`parserfileHandler`、`loadChannelList`。
3. 原文本身的问题未改：非原始字符串里的 `\d`（SyntaxWarning）；`tools.RTCToTimestamp` 的 `and/or` 与闰年判断（见上次交付的 `tools.py`）。
