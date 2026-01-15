# 朋友圈发布器模块结构图

## 模块依赖关系

```
┌─────────────────────────────────────────────────────────────────┐
│                    core/moment_sender.py                         │
│                   （向后兼容层，165行）                           │
│                                                                   │
│  from core.moment import MomentSender, SendResult, ...          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    core/moment/__init__.py                       │
│                      （模块导出，60行）                          │
│                                                                   │
│  导出: MomentSender, SendResult, 各种Handler, ElementLocator   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────┐
        │      core/moment/sender.py              │
        │      （主发送器，468行）                │
        │                                          │
        │  • MomentSender                         │
        │  • SendResult                           │
        │  • 整合所有处理器                        │
        │  • 步骤执行控制                          │
        │  • 错误处理                              │
        └─────────────────────────────────────────┘
                     │
        ┌────────────┼────────────┬────────────┬─────────────┐
        ▼            ▼            ▼            ▼             ▼
┌──────────────┐ ┌────────────┐ ┌──────────┐ ┌────────────┐ ┌──────────────┐
│ WindowHandler│ │ImageHandler│ │TextHandler│ │PublishHand.│ │ElementLocator│
│   (344行)    │ │  (351行)   │ │ (172行)  │ │  (689行)   │ │   (267行)    │
├──────────────┤ ├────────────┤ ├──────────┤ ├────────────┤ ├──────────────┤
│• 窗口导航    │ │• 添加图片  │ │• 输入文案│ │• 打开编辑框│ │• 图像识别    │
│• 窗口调整    │ │• 文件对话框│ │• 剪贴板  │ │• 点击发表  │ │• 混合定位    │
│• 返回主界面  │ │• v3/v4支持│ │• 查找输入│ │• 等待完成  │ │• 多置信度    │
│• 状态检测    │ │• 图片验证  │ │  框      │ │• 查看评论  │ │• 相对定位    │
│              │ │            │ │          │ │• 取消编辑  │ │              │
└──────────────┘ └────────────┘ └──────────┘ └────────────┘ └──────────────┘
```

## 模块职责分配

### 核心模块（sender.py - 468行）
- **MomentSender**: 主发送器类
- **SendResult**: 发送结果数据类
- 整合所有处理器
- 步骤执行控制
- 错误处理和截图

### 窗口管理（window_handler.py - 344行）
- 导航到朋友圈（支持 v3/v4）
- 调整窗口位置和大小
- 返回主界面
- 窗口状态检测

### 图片处理（image_handler.py - 351行）
- 添加图片到朋友圈
- 文件对话框操作（v4）
- 剪贴板粘贴（v3）
- 图片验证和过滤

### 文案处理（text_handler.py - 172行）
- 输入文案到编辑框
- 通过剪贴板操作
- 查找文本输入框

### 发布操作（publish_handler.py - 689行）
- 打开编辑框（图文/纯文字）
- 点击发表按钮
- 等待发布完成
- 发布后查看和评论
- 取消编辑

### 元素定位（locator.py - 267行）
- 图像识别定位
- 混合定位策略
- 多置信度尝试
- 相对位置计算

## 发布流程

```
1. 用户调用
   └─> MomentSender.send_moment(content)

2. 激活微信
   └─> WeChatController.activate_window()

3. 导航到朋友圈
   └─> WindowHandler.navigate_to_moment()

4. 打开编辑框
   └─> PublishHandler.open_compose_dialog()

5. 添加图片（如有）
   └─> ImageHandler.add_images()

6. 输入文案
   └─> TextHandler.input_text()

7. 点击发表
   └─> PublishHandler.click_publish()

8. 等待完成
   └─> PublishHandler.wait_for_publish_complete()

9. 查看评论（可选）
   └─> PublishHandler.view_published_moment()
       └─> ElementLocator.find_dots_button_hybrid()

10. 返回主界面
    └─> WindowHandler.return_to_main()

11. 返回结果
    └─> SendResult
```

## 向后兼容性

### 旧方式（仍然可用）
```python
from core.moment_sender import MomentSender, SendResult
sender = MomentSender()
result = sender.send_moment(content)
```

### 新方式（推荐）
```python
from core.moment import MomentSender, SendResult
sender = MomentSender()
result = sender.send_moment(content)
```

### 高级用法
```python
from core.moment import (
    WindowHandler,
    ImageHandler,
    TextHandler,
    PublishHandler,
    ElementLocator
)
```

## 模块优势

1. **代码结构清晰** - 每个模块职责单一
2. **易于测试** - 可以单独测试每个模块
3. **易于维护** - 问题定位更快速
4. **易于扩展** - 添加新功能不影响现有模块
5. **代码复用** - 各处理器可在其他场景复用

## 文件统计

| 文件 | 行数 | 说明 |
|------|------|------|
| locator.py | 267 | 元素定位 |
| window_handler.py | 344 | 窗口管理 |
| image_handler.py | 351 | 图片处理 |
| text_handler.py | 172 | 文案处理 |
| publish_handler.py | 689 | 发布操作 |
| sender.py | 468 | 主发送器 |
| __init__.py | 60 | 模块导出 |
| **总计** | **2351** | **含完整文档** |
| 原文件 | 1752 | 单一文件 |
| **增加** | **+599** | **+34%** |
