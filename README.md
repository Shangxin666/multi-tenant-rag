# Multi-tenant authentication backend — M2

Python venv + pip、FastAPI、SQLAlchemy 2.x Async、asyncpg、Alembic、
PostgreSQL 17 + pgvector。M2 实现 Tenant/User 注册、JWT 登录与 Tenant admin 查询。
不包含 RLS、Refresh Token、RAG 或业务知识库模块。

## 本地环境（PowerShell）

需要 Python 3.11+、Docker Desktop（Linux containers）。在仓库根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
Copy-Item .env.example .env
```

已有 .env 时不要覆盖。设置非空 POSTGRES_PASSWORD 和随机 JWT_SECRET。
JWT_SECRET 至少 32 字节，应使用安全随机值；没有默认 Secret。
.env 和 .venv 被 Git 忽略，.env.example 可以提交。
生产环境从环境变量注入，环境变量优先于当前目录 .env。

配置：
- DB_HOST=127.0.0.1、DB_PORT=5433；Compose 映射固定 5433 → 5432。
- POSTGRES_DB / POSTGRES_USER / POSTGRES_PASSWORD：开发库配置。
- JWT_SECRET：HS256 签名密钥；不要记录或提交。
- JWT_ALGORITHM：只能是 HS256。
- ACCESS_TOKEN_EXPIRE_MINUTES：默认 30，范围 1–1440。
- TEST_DATABASE_NAME：显式指定独立测试库，例如 rag_test，必须以 _test 结尾。
- DB_ECHO 默认 false；SQLAlchemy 隐藏 SQL 参数，应用不记录请求 Body 或 Authorization。

## 启动与迁移

```powershell
docker compose up -d --wait db
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

打开 http://127.0.0.1:8000/docs，或验证健康检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
docker compose ps
```

/health 返回 200 和 {"status":"ok"}，不访问数据库。
数据库使用命名卷和 pg_isready。初始化完成后的账号密码不会因修改 .env 自动更新。
不要为了修复密码配置而删除数据卷。

0001 只启用 vector，保持历史内容不变；0002 创建 tenants/users。
迁移由明确的命令执行，应用不自动迁移，不调用 create_all。
0002 的 downgrade 会删除这两个业务表；只在可丢弃环境执行。
0001 的 downgrade 保留共享 vector 扩展。

## API

| API | 请求 | 成功响应 |
| --- | --- | --- |
| POST /auth/register | JSON: tenant_name, tenant_slug, email, password | 201: tenant + user |
| POST /auth/login | JSON: email, password | 200: access_token + token_type |
| GET /auth/me | Authorization: Bearer token | 200: UserPublic |
| GET /users | Bearer；admin；limit 默认 50、最大 100，offset 默认 0 | 200: UserPublic 数组 |

通过 /docs 执行 register → login，然后把 access_token 填入 Authorize 的 Bearer 输入框，
调用 me 和 users。登录只提供 JSON，不实现 OAuth2 表单接口。

TenantPublic: id、name、slug、created_at。
UserPublic: id、tenant_id、email、role、is_active、created_at。
这些公开 Schema 不含 password 或 password_hash。
所有输入 Schema 拒绝额外字段；注册无法指定 role、tenant_id 或 is_active。

注册密码长度 12–128，使用 SecretStr；不 trim 密码。
email 在注册和登录入口统一 strip + lower，全局唯一。
Tenant slug strip + lower，长度 1–63，仅允许字母数字及中间连字符。
Tenant name 长度 1–100。输入错误 422，email/slug 冲突统一 409。
登录错误、账号不存在或 inactive 统一 401，不返回具体原因。
未认证、无效/过期 Token 401 并附带 WWW-Authenticate: Bearer；非 admin 403。

## 模型、事务与认证

Tenant: UUID id、name、唯一 slug、带时区 created_at。
User: UUID id、tenant_id 外键、全局唯一 email、Argon2 password_hash、
admin/member role CHECK、is_active、带时区 created_at。
tenant_id 有索引；外键 ON DELETE RESTRICT。email 没有 lower/trim CHECK。
所有其他写入入口未来也必须遵守 email 规范化约定。

注册在 hash 完成后开始单一 Session 事务：Tenant add/flush → User add/flush →
事务退出 commit。User 写入失败会回滚已 flush 的 Tenant；提交后才返回 201。
get_db 提供独立 Session 并关闭，不自动提交。沿用模块级 Engine/sessionmaker，
应用关闭时 dispose，不共享并发请求的 Session。

pwdlib 使用 Argon2id，hash 和 verify 在线程池执行。账号不存在时验证 dummy hash，
减少明显时序差异；不保证完全消除侧信道。
JWT 仅含 sub（User UUID）和 exp，使用固定 HS256 验签并要求两个 claim 都存在。
get_current_user 每请求按 sub 查数据库并检查 active；require_admin 使用数据库最新 role。
Token 不含 role/tenant_id。角色修改或停用在后续请求生效。

/users 只查询 current_user.tenant_id，客户端参数不能切换 Tenant。
M2 没有成员创建或角色管理 API，测试通过 fixture 构造成员。

## 独立测试数据库

M2 集成测试不再使用开发库。保持 APP_ENV=local，在 .env 显式设置
TEST_DATABASE_NAME=rag_test（必须不同于 POSTGRES_DB，且连接目标为本机）。

```powershell
docker compose up -d --wait db
.\.venv\Scripts\python.exe scripts/prepare_test_database.py
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m pytest -m integration
.\.venv\Scripts\python.exe -m pytest -o "addopts="
```

prepare_test_database.py 只创建指定测试库；已有库保留，账号需要 CREATEDB 权限。
集成测试 fixture 首先在该库执行 Alembic upgrade head，再用独立请求 Session 运行测试。
每个用例前后 TRUNCATE users、tenants；仅允许明确指定、不同于开发库、
后缀为 _test 的本机数据库，并在清理前核对 current_database()。
不要把有价值的数据放入测试库。当前串行运行，不支持多个测试进程共用同一库。

默认 pytest 只运行单元测试；-m integration 显式运行数据库测试；
-o "addopts=" 运行全部测试。数据库不可用会报错，不静默跳过。
测试覆盖注册 hash、唯一冲突、事务整体回滚、登录、JWT 无效/过期、
数据库最新权限、member 403、跨 Tenant 隔离、响应字段及迁移约束。
单元测试中的配置和密码随机生成，不读取真实 Secret。

## 安全边界 / TODO

- tenant_id filter 只是应用层隔离，不是最终数据库级安全方案。
  PostgreSQL RLS 将在后续 Milestone 单独实现和测试。
- 当前没有 Refresh Token、Token blacklist、密码重置、邮箱验证或第三方 OAuth。
- 没有速率限制和注册防滥用，不能据此认为已经满足公开生产部署要求。
- JWT 是签名而非加密，生产必须 HTTPS；保护客户端 Token 存储。
- 更完整的 FastAPI 422 校验错误 input 脱敏属于后续 Security Hardening。
  SecretStr 不保证原始无效输入在默认校验错误响应中被隐藏。
- 数据库直接写入不强制 email 小写；未来写入口必须统一规范化。
- 生产数据库应用账号与迁移账号应分权，后续完善密钥轮换与审计。
- pip 使用依赖兼容范围，无锁文件；不同时间解析的依赖版本可能不同。
