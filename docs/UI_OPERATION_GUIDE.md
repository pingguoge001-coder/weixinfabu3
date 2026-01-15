# 微信自动化操作要点指南

> **文档目的**: 记录手搓调试出来的 UI 操作经验和定位技巧，方便代码改进时参考
>
> **更新时间**: 2025-12-09
>
> **适用版本**: 微信 PC 版 v3.9.x / v4.0+

---

## 一、微信版本差异

### 1.1 窗口类名对比

| 元素 | v3.9.x | v4.0+ |
|------|--------|-------|
| 主窗口 | `WeChatMainWndForPC` | `mmui::MainWindow` |
| 朋友圈窗口 | `SnsWnd` | `mmui::SNSWindow` (独立窗口) |
| 发布编辑窗口 | `SnsUploadWnd` | 在主窗口内 |
| 输入框 | `RichEdit20W` | `mmui::XTextEdit` |
| 搜索框 | `SearchEdit` | `mmui::XLineEdit` |
| 按钮 | - | `mmui::XButton` |

### 1.2 导航栏差异

**v3.9.x:**
- 导航栏在窗口左侧，包含：微信、通讯录、收藏、**发现**（朋友圈在发现子菜单）

**v4.0+:**
- 导航栏包含：微信、通讯录、收藏、**朋友圈**（直接入口）、视频号、看一看等
- 朋友圈是独立按钮，无需先点"发现"

---

## 二、朋友圈发布操作

### 2.1 发布流程 (v4.0)

```
1. 激活微信主窗口
2. 双击导航栏"朋友圈"按钮 → 打开独立窗口 (mmui::SNSWindow)
3. 点击顶部"发表"按钮 → 进入发布界面
4. 点击"添加图片"按钮 (mmui::PublishImageAddGridCell) → 弹出文件对话框
5. 在文件对话框中选择图片
6. 输入文案到输入框 (mmui::ReplyInputField)
7. 点击"发表"按钮完成发布
```

### 2.2 关键定位技巧

#### 2.2.1 "发表"按钮定位

**问题**: 页面上可能有多个"发表"按钮（顶部和底部）

**解决方案**:
```python
# 选择 Y 坐标最大的（底部的按钮）
buttons = []
for i in range(10):
    btn = window.ButtonControl(foundIndex=i+1, Name="发表")
    if btn.Exists(0, 0):
        rect = btn.BoundingRectangle
        buttons.append((btn, rect.top))

# 排序取底部按钮
buttons.sort(key=lambda x: x[1], reverse=True)
submit_btn = buttons[0][0]
```

#### 2.2.2 "..." 按钮定位 (朋友圈详情页)

**问题**: "..." 按钮的 Y 坐标随朋友圈内容长度变化

**解决方案 - 混合定位策略** (优先级从高到低):

1. **删除按钮定位法** (最可靠)
   ```python
   # 删除按钮（垃圾桶）和 "..." 按钮在同一行
   # 找到删除按钮获取 Y 坐标，"..." 的 X 坐标固定

   template_path = "data/templates/delete_btn.png"
   location = pyautogui.locateOnScreen(template_path, confidence=0.7)
   if location:
       center = pyautogui.center(location)
       dots_x = window_rect.right - 55  # 固定 X 偏移
       dots_y = center.y  # 与删除按钮同行
   ```

2. **时间戳相对定位**
   ```python
   # 时间戳格式: HH:MM, 昨天, X小时前, X分钟前 等
   # "..." 在时间戳右侧约 40px

   time_patterns = [r'^\d{1,2}:\d{2}$', r'^昨天$', r'^\d+小时前$']
   # 找到时间戳控件后
   dots_x = timestamp_rect.right + 40
   dots_y = timestamp_rect.center_y
   ```

3. **坐标后备**
   ```python
   # 基于窗口位置的固定偏移
   dots_x = window_rect.right - 55
   dots_y = window_rect.top + 864
   ```

#### 2.2.3 头像区域定位 (进入个人朋友圈)

**位置**: 朋友圈窗口的右上角区域

```python
# 相对于窗口的坐标
avatar_x = window_rect.right - 110  # 距右边 110px
avatar_y = window_rect.top + 400    # 距顶部 400px

# 点击后等待 1 秒，再点击"朋友圈"区域
moment_x = avatar_x + 400
moment_y = avatar_y + 200
```

### 2.3 图片添加方式

#### v4.0 - 文件对话框方式

```python
# 1. 点击"添加图片"按钮
add_btn = window.Control(ClassName="mmui::PublishImageAddGridCell")
add_btn.Click()

# 2. 等待文件对话框
file_dialog = auto.WindowControl(ClassName="#32770", Name="打开")

# 3. 导航到图片文件夹
pyautogui.hotkey('ctrl', 'l')  # 选中地址栏
pyperclip.copy(folder_path)
pyautogui.hotkey('ctrl', 'v')  # 粘贴路径
pyautogui.press('enter')

# 4. 输入文件名
filename_input = file_dialog.EditControl(AutomationId="1148")
pyautogui.hotkey('ctrl', 'a')
pyperclip.copy(filename)
pyautogui.hotkey('ctrl', 'v')

# 5. 点击打开
open_btn = file_dialog.ButtonControl(Name="打开(O)")
open_btn.Click()
```

#### v3.x - 剪贴板粘贴方式

```python
# 直接通过剪贴板粘贴图片
from PIL import Image
image = Image.open(image_path)
clipboard.set_image(image)
pyautogui.hotkey('ctrl', 'v')
```

---

## 三、群发消息操作

### 3.1 发送流程

```
1. 激活微信主窗口
2. Ctrl+F 打开搜索
3. 输入群名搜索
4. 从搜索结果进入群聊
5. 定位消息输入框
6. 发送图片（如有）
7. 发送文案
8. 返回主界面
```

### 3.2 关键定位技巧

#### 3.2.1 搜索框定位

```python
# 优先按名称查找
search_box = window.EditControl(searchDepth=10, Name="搜索")

# v4 备选
search_box = window.EditControl(searchDepth=10, ClassName="mmui::XLineEdit")

# v3 备选
search_box = window.EditControl(searchDepth=10, ClassName="SearchEdit")
```

#### 3.2.2 消息输入框定位

```python
# v4
input_box = window.EditControl(searchDepth=15, ClassName="mmui::XTextEdit")

# v3
input_box = window.EditControl(searchDepth=15, ClassName="RichEdit20W")
```

#### 3.2.3 "发送文件"按钮定位 (v4)

```python
# 重要: 需要较大的 searchDepth (25)
btn = window.ButtonControl(
    searchDepth=25,
    ClassName="mmui::XButton",
    Name="发送文件"
)
```

### 3.3 群名搜索匹配

```python
# 遍历搜索结果，优先精确匹配
for i in range(20):
    item = window.ListItemControl(searchDepth=10, foundIndex=i+1)
    if item.Exists(0.5, 0):
        item_name = item.Name
        if item_name == group_name:  # 精确匹配
            item.Click()
            return True
        elif group_name in item_name:  # 部分匹配
            found_item = item

# 未找到精确匹配时，选择第一个结果
auto.SendKeys("{Enter}")
```

---

## 四、通用操作技巧

### 4.1 元素查找超时设置

```python
# 推荐超时设置
ELEMENT_TIMEOUT = 10  # 元素查找超时（秒）
PUBLISH_TIMEOUT = 30  # 发布超时（秒）

# 使用方式
element.Exists(timeout_seconds, retry_interval)
# 例如: btn.Exists(10, 1) 表示最多等10秒，每秒检查一次
```

### 4.2 操作间隔时间

```python
STEP_DELAY = 0.8      # 步骤间隔
SHORT_DELAY = 0.3     # 短延迟（如点击后）
LONG_DELAY = 1.5      # 长延迟（如页面切换）
PAGE_LOAD_DELAY = 2.0 # 页面加载延迟
PUBLISH_WAIT = 3.0    # 发布等待时间
```

### 4.3 剪贴板操作

```python
# 备份 -> 操作 -> 恢复
clipboard.backup()
try:
    clipboard.set_text(text)
    pyautogui.hotkey('ctrl', 'v')
finally:
    clipboard.restore()
```

### 4.4 中文输入

**问题**: 直接 `SendKeys()` 不支持中文

**解决方案**: 使用剪贴板
```python
pyperclip.copy(chinese_text)
pyautogui.hotkey('ctrl', 'v')
```

### 4.5 窗口激活

```python
# 先查找窗口
window = auto.WindowControl(ClassName="mmui::MainWindow")

# 激活方式1: SetFocus()
window.SetFocus()

# 激活方式2: SwitchToThisWindow
import win32gui
hwnd = window.NativeWindowHandle
win32gui.SetForegroundWindow(hwnd)
```

---

## 五、错误处理要点

### 5.1 常见异常情况

| 异常 | 检测方式 | 处理方法 |
|------|----------|----------|
| 弹窗遮挡 | 检测 `#32770` 类窗口 | 关闭弹窗或按 ESC |
| 元素不存在 | `Exists()` 返回 False | 保存截图，记录日志 |
| 搜索无结果 | 检测 `Name="无搜索结果"` | 跳过该群，继续下一个 |
| 发送失败 | 检测 `Name="重新发送"` 按钮 | 重试或标记失败 |
| 网络错误 | 检测 `Name="网络错误"` | 等待重试 |

### 5.2 截图保存

```python
def save_error_screenshot(name: str):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = f"screenshots/{name}_{timestamp}.png"
    screenshot = pyautogui.screenshot()
    screenshot.save(filepath)
    return filepath
```

### 5.3 回滚操作

```python
# 关闭可能打开的窗口
pyautogui.press('escape')  # 关闭弹窗/对话框

# 强制关闭窗口
pyautogui.hotkey('alt', 'F4')

# 返回主界面
window.ButtonControl(Name="返回").Click()
```

---

## 六、配置参数

### 6.1 config.yaml 中的定位参数

```yaml
ui_location:
  # "..." 按钮定位
  dots_btn_right_offset: 55      # 距窗口右边的像素
  dots_btn_top_offset: 864       # 坐标后备的 Y 偏移
  dots_timestamp_offset: 40      # 时间戳右侧偏移

  # 发送按钮定位
  send_btn_x_offset: 80          # 发送按钮 X 偏移

  # 关闭按钮定位
  close_btn_offset: 15           # 关闭按钮偏移

  # 图像识别置信度
  image_confidence_levels: [0.8, 0.6, 0.4]
```

### 6.2 selectors.yaml 结构

```yaml
v4.0:
  main_window:
    class_name: "mmui::MainWindow"
    title: "微信"

  navigation:
    moments_button:
      name: "朋友圈"
      class_name: "mmui::XTabBarItem"
      control_type: "Button"

  group_chat:
    search_box:
      name: "搜索"
      class_name: "mmui::XLineEdit"
      control_type: "Edit"

    send_file_button:
      name: "发送文件"
      class_name: "mmui::XButton"
      control_type: "Button"
      search_depth: 25  # 重要：深度搜索
```

---

## 七、模板图片

存放位置: `data/templates/`

| 文件名 | 用途 | 说明 |
|--------|------|------|
| `delete_btn.png` | 删除按钮（垃圾桶） | 用于定位 "..." 按钮的 Y 坐标 |
| `dots_btn.png` | "..." 按钮 | 直接图像识别（备用） |
| `send_btn.png` | 发送按钮 | 评论发送按钮识别 |

**图像识别参数**:
- 推荐置信度: 0.7
- 尝试顺序: [0.8, 0.7, 0.6, 0.5]

---

## 八、调试工具

### 8.1 UI 元素检测脚本

```python
# detect_window.py - 检测微信窗口元素
import uiautomation as auto

def print_tree(ctrl, depth=0, max_depth=5):
    if depth > max_depth:
        return
    print("  " * depth + f"{ctrl.ControlTypeName}: {ctrl.Name} ({ctrl.ClassName})")
    for child in ctrl.GetChildren():
        print_tree(child, depth + 1, max_depth)

# 使用
window = auto.WindowControl(ClassName="mmui::MainWindow")
print_tree(window)
```

### 8.2 坐标测试

```python
import pyautogui
import time

# 实时显示鼠标位置
while True:
    x, y = pyautogui.position()
    print(f"位置: ({x}, {y})", end="\r")
    time.sleep(0.1)
```

---

## 九、实战经验总结

### 9.1 v4 发送图片的关键步骤

```python
# 完整流程（关键点已标注）

# 1. 必须先激活窗口，再操作按键
self._main_window.SetFocus()
time.sleep(0.3)

# 2. 点击输入框会自动关闭搜索框
input_box = self._find_input_box()
if input_box:
    input_box.Click()
    time.sleep(0.3)

# 3. 等待 UI 稳定（重要！）
time.sleep(0.5)

# 4. 查找"发送文件"按钮，需要较大 searchDepth
send_file_btn = window.ButtonControl(
    searchDepth=25,  # 关键：需要深度搜索
    ClassName="mmui::XButton",
    Name="发送文件"
)

# 5. 文件对话框可能有两个名称
file_dialog = auto.WindowControl(searchDepth=2, Name="打开")
if not file_dialog.Exists(5, 1):
    file_dialog = auto.WindowControl(searchDepth=2, ClassName="#32770")

# 6. 导航到文件夹：Ctrl+L 选中地址栏
pyautogui.hotkey('ctrl', 'l')  # 不是 Ctrl+D！
time.sleep(0.3)

# 7. 批量选择文件：用空格分隔的带引号文件名
files_str = " ".join(f'"{Path(path).stem}"' for path in valid_paths)
# 结果如: "img1" "img2" "img3"

# 8. 文件名输入框可能是 ComboBox
edit = file_dialog.ComboBoxControl(searchDepth=10, Name="文件名(N):")
if not edit.Exists(3, 1):
    edit = file_dialog.EditControl(searchDepth=10)  # 备选
```

### 9.2 发送失败检测

```python
# 检查"重新发送"按钮是否出现
fail_btn = window.ButtonControl(searchDepth=15, Name="重新发送")
if fail_btn.Exists(0.5, 0):
    logger.warning("检测到发送失败")
    return False

# 检查进度条（发送中状态）
progress = window.ProgressBarControl(searchDepth=15)
if progress.Exists(0.3, 0):
    # 还在发送中，继续等待
    time.sleep(0.5)
```

### 9.3 v3 vs v4 版本降级

```python
# 当 v4 方式失败时，自动降级到 v3
if self._is_v4:
    result = self._send_images_v4(image_paths)
    if result == 0:
        logger.warning("v4方式失败，降级到剪贴板方式")
        result = self._send_images_v3(image_paths)
```

### 9.4 ESC 键使用注意

```python
# 单次 ESC：关闭搜索框/弹窗
auto.SendKeys("{Escape}")

# 注意：多次 ESC 可能导致微信最小化！
# 错误示例：
for _ in range(3):  # 危险！
    auto.SendKeys("{Escape}")
```

### 9.5 搜索后选择群的技巧

```python
# 1. 优先精确匹配
for i in range(20):
    item = window.ListItemControl(foundIndex=i+1)
    if item.Name == group_name:  # 精确匹配
        item.Click()
        return True

# 2. 未找到精确匹配时，直接按 Enter 选择第一个
auto.SendKeys("{Enter}")
```

---

## 十、注意事项

1. **窗口遮挡**: 确保微信窗口不被其他窗口遮挡
2. **分辨率**: 建议使用 >= 1920x1080 分辨率
3. **DPI 缩放**: 100% 缩放最稳定，高 DPI 可能导致坐标偏移
4. **微信更新**: 微信版本更新可能导致类名变化，需及时调整
5. **操作速度**: 不要过快，保证每步操作完成后再进行下一步
6. **SetFocus 顺序**: 必须先 SetFocus 窗口，再发送按键
7. **searchDepth**: 不同元素需要不同深度，"发送文件"需要 25
8. **剪贴板恢复**: 使用剪贴板后务必恢复，避免影响用户数据

---

## 十一、快速参考表

### 11.1 元素定位参数速查

| 元素 | searchDepth | 定位方式 | 备注 |
|------|-------------|----------|------|
| 消息输入框 | 15 | ClassName | v4: `mmui::XTextEdit` |
| 搜索框 | 10 | Name="搜索" | 优先按名称 |
| 发送文件按钮 | 25 | ClassName+Name | 深度搜索 |
| 发表按钮 | 10 | Name="发表" | 可能有多个 |
| 列表项 | 10 | foundIndex | 遍历搜索 |

### 11.2 延时参数速查

| 操作 | 延时（秒） | 说明 |
|------|------------|------|
| 点击后 | 0.3 | 短延时 |
| 页面切换 | 0.8 | 步骤间隔 |
| 搜索等待 | 1.0 | 等待搜索结果 |
| 对话框打开 | 0.5 | 等待 UI 稳定 |
| 文件选择后 | 1.5 | 等待文件加载 |
| 发送后 | 1.0 | 等待发送完成 |

### 11.3 快捷键速查

| 功能 | 快捷键 | 说明 |
|------|--------|------|
| 打开搜索 | Ctrl+F | 通用 |
| 全选 | Ctrl+A | 输入框内 |
| 粘贴 | Ctrl+V | 文本/图片 |
| 地址栏 | Ctrl+L | 文件对话框 |
| 关闭 | ESC | 单次 |
| 强制关闭 | Alt+F4 | 窗口 |
| 确认 | Enter | 对话框 |
