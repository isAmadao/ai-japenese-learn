# 011 · 注册安全升级（邮箱验证 + CAPTCHA + JWT 刷新 + 忘记密码）

- **日期**: 2026-06-14
- **状态**: ✅ 已采纳

## 背景

之前用户注册只有用户名+密码，无邮箱验证，存在以下问题：
- 无法找回密码
- 无法确认用户身份真实性
- 容易被机器人批量注册
- 无登录失败防护

## 方案

### 一、邮箱验证注册

**User 模型新增字段：**
```python
email = Column(String(120), unique=True, index=True)  # 邮箱
is_verified = Column(Boolean, default=False)           # 邮箱已验证
```

**注册流程：**
```
填写表单（昵称+邮箱+密码）
    → 真人验证（随机：数学计算 / Emoji选择 / 颜色选择）
    → 发送验证码到邮箱（30s 冷却）
    → 输入 6 位验证码
    → 注册完成，显示账号信息
```

**CAPTCHA 三种类型随机切换：**
| 类型 | 示例 | 验证方式 |
|------|------|---------|
| 数学 | `15 - 4 = ?` | 输入数字答案 |
| Emoji | 请点击「星星」 | 从 4 个 emoji 中选择 |
| 颜色 | 请选择「绿色」 | 从 4 个颜色名称中选择 |

### 二、登录安全

- **三次失败→CAPTCHA**：Redis 计数器，15 分钟窗口，第 4 次起要求真人验证
- **支持邮箱/用户名登录**：自动识别
- **忘记密码**：邮箱验证 → 重置密码

### 三、JWT 刷新机制

- Access token: 1 小时（原 30 天）
- Refresh token: 7 天（UUID 存 Redis，支持轮转）
- 前端 401 拦截器自动刷新，多并发队列安全

### 四、密码强度提示

注册和设置页实时显示强度条：`弱 / 中 / 强 / 非常强`

### 五、个人设置页

新增 `/settings` 页面：
- 查看邮箱/验证状态
- 修改昵称
- 修改密码（需当前密码）

### 六、记住登录状态

勾选 → localStorage 持久化；不勾选 → sessionStorage（关闭浏览器即清除）

### 七、其他改进

- Redis 不可用时即时降级（`socket_connect_timeout=1` + 跳过重试）
- `.env` 从项目根目录加载（修复 Docker 下配置不生效）

## 技术细节

### SMTP 配置

```env
SMTP_HOST=smtp.qq.com
SMTP_PORT=587
SMTP_USER=your-email@qq.com
SMTP_PASSWORD=your-authorization-code
```

未配置时自动降级为日志输出（开发模式）。

### Token 旋转

每次调用 `/auth/refresh` 返回新 access + 新 refresh，旧 refresh 立即失效。

### 本地缓存降级

Redis 不可用时所有接口自动降级为进程内内存缓存（`_LocalCache`），通过检查 `_async_client is None` 避免每次操作都尝试连接 Redis（避免 Windows 下 4s 超时）。

## 后果

**正面：**
- 注册安全性大幅提升（真人验证 + 邮箱确认）
- 登录防护（暴力破解防护）
- 找回密码不再是难题
- JWT 安全提升（短寿命 + 刷新 + 轮转）
- 开发体验提升（SMTP 降级 + Redis 降级）

**负面：**
- 注册流程变长（但可接受，常见做法）
- 需配置 SMTP 才能发送真实邮件
- Redis 不可用时 refresh token 在本地缓存，进程重启后需重新登录

## 关联决策

- [JWT 认证系统](016-jwt-auth.md)
- [Redis 缓存系统](006-agent-redis-cache.md)
