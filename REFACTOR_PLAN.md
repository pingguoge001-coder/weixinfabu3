# 微信发布项目 - 代码优化方案

> 核心原则：**测试与优化同步，不影响现有功能**

---

## 一、当前代码问题总结

### 1.1 文件过长

| 文件 | 行数 | 问题 |
|------|------|------|
| core/moment_sender.py | ~1,400 | 职责过多，难以维护 |
| core/wechat_controller.py | ~1,000 | 窗口控制+进程管理+截图混在一起 |
| gui/main_window.py | ~900 | UI 与业务逻辑耦合 |
| services/config_manager.py | ~1,100 | 加载+验证+加密+监听混在一起 |

### 1.2 GUI 与业务耦合

`gui/main_window.py` 直接初始化和操作：
- 数据库 (Database)
- 调度器 (TaskScheduler)
- 队列管理 (QueueManager)
- 发布执行逻辑

### 1.3 代码重复

- `MomentSender` 和 `GroupSender` 有相似的发布流程
- 多处相同的异常处理模式
- 元素查找逻辑重复

### 1.4 异常处理过于宽泛

多处使用 `except Exception`，缺少具体异常类型和结构化日志。

### 1.5 测试覆盖不足

- `core/` 模块：0% 覆盖
- `gui/` 模块：0% 覆盖
- 其他模块：有基础测试

### 1.6 存在旧版副本

`wechat-auto-sender/` 目录是旧版代码拷贝，应清理。

---

## 二、优化优先级排序

### P0 - 零风险（立即可做）

| 序号 | 优化项 | 风险 | 预计耗时 |
|------|--------|------|---------|
| 1 | 删除 wechat-auto-sender/ 旧版目录 | 无 | 5分钟 |
| 2 | 添加类型提示 | 无 | 按需 |
| 3 | 补充代码注释 | 无 | 按需 |

### P1 - 低风险（需要测试保护）

| 序号 | 优化项 | 风险 | 前置条件 |
|------|--------|------|---------|
| 4 | 提取公共工具方法 | 低 | 补充相关测试 |
| 5 | 创建自定义异常类 | 低 | 不改变现有逻辑 |
| 6 | 细化异常处理 | 低 | 逐个替换验证 |

### P2 - 中风险（需要充分测试）

| 序号 | 优化项 | 风险 | 前置条件 |
|------|--------|------|---------|
| 7 | 拆分 wechat_controller.py | 中 | 先补单元测试 |
| 8 | 拆分 moment_sender.py | 中 | 先补单元测试 |
| 9 | 提取 Moment/Group 共同逻辑 | 中 | 先补单元测试 |

### P3 - 高风险（最后处理）

| 序号 | 优化项 | 风险 | 前置条件 |
|------|--------|------|---------|
| 10 | 分离 main_window.py 业务逻辑 | 高 | 需要 GUI 测试 |
| 11 | 引入依赖注入 | 高 | 全面测试覆盖 |

---

## 三、具体优化步骤

### 优化项 1：删除旧版目录

```
步骤：
1. 确认 wechat-auto-sender/ 未被引用
2. 删除整个目录
3. 运行现有测试验证
4. 提交: "chore: 删除旧版代码副本"
```

---

### 优化项 2-3：类型提示和注释

```
步骤：
1. 选择一个文件
2. 添加类型提示/注释
3. 运行 mypy 检查（可选）
4. 提交: "docs: 补充 xxx 模块类型提示"
```

---

### 优化项 4：提取公共工具方法

**目标文件**: 创建 `core/utils/element_helper.py`

```
步骤：
1. [测试] 为现有元素查找逻辑写测试
2. [重构] 提取重复的元素查找代码到工具类
3. [验证] 运行测试确认功能正常
4. [提交] "refactor: 提取元素查找工具类"
```

---

### 优化项 5：创建自定义异常类

**目标文件**: 创建 `core/exceptions.py`

```python
# 异常层次结构
class WeChatException(Exception):
    """微信相关异常基类"""
    pass

class WeChatWindowNotFound(WeChatException):
    """微信窗口未找到"""
    pass

class WeChatLoginRequired(WeChatException):
    """需要登录微信"""
    pass

class ElementNotFound(WeChatException):
    """UI 元素未找到"""
    pass

class PublishTimeout(WeChatException):
    """发布超时"""
    pass

class PublishFailed(WeChatException):
    """发布失败"""
    pass
```

```
步骤：
1. [创建] 新建 core/exceptions.py
2. [验证] 运行现有测试（不应有影响）
3. [提交] "feat: 添加自定义异常类"
```

---

### 优化项 6：细化异常处理

**逐个文件替换**，每次只改一处：

```python
# 之前
try:
    result = self._find_element()
except Exception as e:
    logger.error(f"失败: {e}")

# 之后
try:
    result = self._find_element()
except ElementNotFound as e:
    logger.warning(f"元素未找到: {e}")
except WeChatWindowNotFound as e:
    logger.error(f"微信窗口丢失: {e}")
except Exception as e:
    logger.exception(f"未知错误: {e}")
```

```
步骤：
1. [选择] 选一个 except Exception 位置
2. [分析] 确定可能的具体异常类型
3. [替换] 改为具体异常
4. [验证] 手动测试该功能
5. [提交] "refactor: 细化 xxx 异常处理"
```

---

### 优化项 7：拆分 wechat_controller.py

**拆分方案**：

```
core/wechat_controller.py (1000行)
    ↓ 拆分为
core/wechat/
├── __init__.py
├── window_manager.py      # 窗口查找、激活
├── process_manager.py     # 进程启动、检测
├── screen_capture.py      # 截图功能
└── controller.py          # 主控制器（组合上述模块）
```

```
步骤：
1. [测试] 为 WeChatController 主要方法写单元测试
2. [创建] 新建 core/wechat/ 目录结构
3. [提取] 逐个提取方法到新模块
4. [验证] 每提取一个就运行测试
5. [提交] "refactor: 拆分 wechat_controller"
```

---

### 优化项 8：拆分 moment_sender.py

**拆分方案**：

```
core/moment_sender.py (1400行)
    ↓ 拆分为
core/moment/
├── __init__.py
├── navigator.py          # 导航到朋友圈
├── content_input.py      # 输入文案
├── image_uploader.py     # 上传图片
├── publisher.py          # 发布确认
└── sender.py             # 主发送器（组合上述模块）
```

```
步骤：
1. [测试] 为 MomentSender 主要方法写单元测试
2. [创建] 新建 core/moment/ 目录结构
3. [提取] 逐个提取方法到新模块
4. [验证] 每提取一个就运行测试
5. [提交] "refactor: 拆分 moment_sender"
```

---

### 优化项 9：提取 Moment/Group 共同逻辑

**创建基类**：

```python
# core/publisher_base.py
class PublisherBase(ABC):
    """发布器基类"""

    def publish(self, content: Content) -> SendResult:
        """模板方法"""
        self.activate_window()
        self.navigate()
        self.input_content(content)
        self.confirm()
        return self.verify()

    @abstractmethod
    def navigate(self):
        """导航到发布位置"""
        pass

    @abstractmethod
    def input_content(self, content: Content):
        """输入内容"""
        pass
```

```
步骤：
1. [测试] 确保 Moment 和 Group 发送都有测试覆盖
2. [分析] 找出两者的共同步骤
3. [创建] 创建 PublisherBase 基类
4. [重构] 让 MomentSender 和 GroupSender 继承基类
5. [验证] 运行所有测试
6. [提交] "refactor: 提取发布器基类"
```

---

### 优化项 10：分离 main_window.py 业务逻辑

**拆分方案**：

```
gui/main_window.py (900行)
    ↓ 拆分为
gui/main_window.py        # 纯 UI（~400行）
controllers/
├── __init__.py
├── app_controller.py     # 应用控制器
├── publish_controller.py # 发布控制
└── schedule_controller.py # 调度控制
```

```
步骤：
1. [测试] 为主要功能写集成测试
2. [创建] 创建 controllers/ 目录
3. [提取] 逐步将业务逻辑移到 controller
4. [验证] 每步都运行测试
5. [提交] "refactor: 分离主窗口业务逻辑"
```

---

## 四、回滚方案

### Git 提交策略

```bash
# 每个优化项单独提交
git add .
git commit -m "refactor: xxx"

# 出问题立即回滚
git revert HEAD

# 或回滚到某个稳定版本
git reset --hard <commit-hash>
```

### 检查点

每完成一个优化项后：
1. 运行全部测试：`pytest tests/`
2. 手动测试核心功能：发朋友圈、群发
3. 确认无问题后再继续下一项

### 紧急回滚

如果优化后出现严重问题：
```bash
# 查看提交历史
git log --oneline -10

# 回滚到优化前
git reset --hard <优化前的commit>
```

---

## 五、执行顺序建议

```
Day 1: P0（零风险）
  └── 删除旧版目录、补充注释

Day 2: P1（低风险）
  ├── 创建异常类
  └── 提取工具方法

Day 3-4: 补充测试
  ├── core/wechat_controller.py 测试
  └── core/moment_sender.py 测试

Day 5-6: P2（中风险）
  ├── 拆分 wechat_controller
  └── 拆分 moment_sender

Day 7+: P3（高风险）
  └── 分离 GUI 业务逻辑（可选）
```

---

## 六、验收标准

每个优化项完成后需满足：

- [ ] 所有现有测试通过
- [ ] 新增测试覆盖改动代码
- [ ] 手动测试核心功能正常
- [ ] 代码已提交到 git
- [ ] 可随时回滚到上一版本
