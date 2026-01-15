# 微信控制器快速使用指南

## 快速开始

### 基本使用（推荐）

```python
from core.wechat import get_wechat_controller

# 获取控制器实例（单例）
controller = get_wechat_controller()

# 查找微信窗口
window = controller.find_wechat_window()

# 检查登录状态
status = controller.check_login_status()

# 激活窗口
controller.activate_window()
```

### 向后兼容方式（现有代码）

```python
# 原有导入方式仍然有效
from core.wechat_controller import get_wechat_controller, WeChatController

controller = get_wechat_controller()
```

## 常用操作

### 1. 窗口管理

```python
# 查找主窗口
window = controller.find_wechat_window(timeout=10)

# 激活窗口到前台
controller.activate_window()

# 获取窗口位置和大小
rect = controller.get_window_rect()
print(f"位置: ({rect.left}, {rect.top})")
print(f"大小: {rect.width} x {rect.height}")

# 移动窗口
controller.move_window(x=100, y=100, width=800, height=600)

# 重置到配置的位置
controller.reset_main_window_position()
```

### 2. 登录检测

```python
from core.wechat import WeChatStatus

# 检查登录状态
status = controller.check_login_status()

if status == WeChatStatus.NOT_RUNNING:
    # 启动微信
    controller.start_wechat()

elif status == WeChatStatus.NOT_LOGGED_IN:
    # 等待用户登录
    print("请扫码登录微信")
    controller.wait_for_login(timeout=300)

elif status == WeChatStatus.LOGGED_IN:
    print("微信已登录")
```

### 3. 版本检测

```python
# 获取检测到的版本
version = controller.get_detected_version()

if version == "v4":
    print("微信 4.0+")
elif version == "v3":
    print("微信 3.x")
```

### 4. 小程序操作

```python
# 刷新小程序
controller.refresh_miniprogram()

# 打开产品转发页面并转发到群
controller.open_product_forward(
    content_code="F00619",  # 文案编号
    group_name="测试群"
)
```

### 5. 显示器管理

```python
# 获取所有显示器
monitors = controller.get_monitors()

for i, monitor in enumerate(monitors):
    print(f"显示器 {i+1}:")
    print(f"  主显示器: {monitor.is_primary}")
    print(f"  分辨率: {monitor.rect.width} x {monitor.rect.height}")

# 移动窗口到主显示器
controller.move_window_to_primary()
```

### 6. 截图

```python
# 启用截图（在配置中）
from services.config_manager import get_config_manager
config = get_config_manager()
config.set("advanced.save_screenshots", True)

# 截图
screenshot_path = controller.take_screenshot("my_screenshot")
if screenshot_path:
    print(f"截图已保存: {screenshot_path}")
```

## 高级用法

### 使用子模块

如果需要更细粒度的控制，可以直接使用子模块：

```python
from core.wechat import (
    WindowManager,
    VersionDetector,
    LoginChecker,
    NavigationOperator
)

# 创建窗口管理器
wm = WindowManager()
window = wm.find_window_by_class(
    class_names=["mmui::MainWindow", "WeChatMainWndForPC"],
    timeout=10,
    title_contains="微信"
)

# 创建版本检测器
vd = VersionDetector()
version = vd.detect_version_from_process()
is_running = vd.is_wechat_running()

# 创建登录检查器（需要依赖注入）
lc = LoginChecker(vd, wm)
status = lc.check_login_status(window)

# 创建导航操作器
nav = NavigationOperator()
nav.refresh_miniprogram()
```

## 数据类型

### WeChatStatus（枚举）

```python
from core.wechat import WeChatStatus

WeChatStatus.NOT_RUNNING    # 微信未运行
WeChatStatus.NOT_LOGGED_IN  # 未登录
WeChatStatus.LOGGED_IN      # 已登录
WeChatStatus.LOCKED         # 锁定状态
WeChatStatus.UNKNOWN        # 未知状态
```

### Rect（窗口矩形）

```python
from core.wechat import Rect

rect = controller.get_window_rect()

# 属性
rect.left    # 左边界
rect.top     # 上边界
rect.right   # 右边界
rect.bottom  # 下边界
rect.width   # 宽度
rect.height  # 高度
rect.center  # 中心点 (x, y)
```

### MonitorInfo（显示器信息）

```python
from core.wechat import MonitorInfo

monitors = controller.get_monitors()
monitor = monitors[0]

# 属性
monitor.handle       # 显示器句柄
monitor.is_primary   # 是否为主显示器
monitor.rect         # 显示器矩形区域
monitor.work_rect    # 工作区域（排除任务栏）
```

## 错误处理

```python
try:
    controller = get_wechat_controller()
    window = controller.find_wechat_window(timeout=5)

    if not window:
        print("未找到微信窗口")
        return

    controller.activate_window()

except Exception as e:
    print(f"操作失败: {e}")
    import traceback
    traceback.print_exc()
```

## 配置

主要配置项在 `config.yaml` 中：

```yaml
# 窗口位置和大小
display:
  wechat_window:
    x: 85
    y: 124
    width: 1536
    height: 1080

# 自动化超时
automation:
  timeout:
    window_wait: 15  # 窗口查找超时

# 截图
advanced:
  save_screenshots: true
  screenshot_dir: "screenshots"

# 微信路径（可选，留空则自动查找）
paths:
  wechat_path: ""
```

## 测试

运行测试脚本：

```bash
# 测试主控制器
python core/wechat_controller.py

# 测试导入
python -c "from core.wechat import get_wechat_controller; print('OK')"
```

## 常见问题

### Q: 导入错误怎么办？
A: 确保使用正确的导入路径：
```python
# 推荐方式
from core.wechat import get_wechat_controller

# 向后兼容方式
from core.wechat_controller import get_wechat_controller
```

### Q: 找不到微信窗口？
A: 检查：
1. 微信是否正在运行？
2. 是否已登录？
3. 增加 timeout 参数

### Q: 版本检测不准确？
A: 版本检测基于窗口类名和进程名，通常是准确的。如果有问题，可以手动指定。

### Q: 如何调试？
A: 启用 DEBUG 日志：
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 更多信息

- **详细文档**: 参见 `core/wechat/README.md`
- **拆分说明**: 参见 `REFACTOR_WECHAT_CONTROLLER.md`
- **完整摘要**: 参见 `core/wechat/REFACTOR_SUMMARY.md`
- **异常处理**: 参见 `core/exceptions.py`
- **UI 辅助**: 参见 `core/utils/element_helper.py`
