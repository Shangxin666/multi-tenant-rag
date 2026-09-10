# Multi-tenant RAG — Milestone 1

当前仅实现后端基础设施，不包含业务表、认证、租户隔离或 RAG。

## 环境准备（Windows PowerShell）

安装 Python 3.11+ 和 Docker Desktop（Linux containers），从仓库根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
Copy-Item .env.example .env
```

编辑 .env，设置自己生成的非空 POSTGRES_PASSWORD。不要提交 .env。
无需激活 venv；以下命令直接使用环境内解释器。Linux/macOS 使用 .venv/bin/python。

配置由 Pydantic Settings 读取，环境变量优先于当前工作目录的 .env。
数据库 URL 使用 SQLAlchemy URL API 构造，支持密码中的特殊字符。
不要输出完整连接信息或使用会输出已展开密码的 Compose 配置命令。

## 启动

```powershell
docker compose up -d --wait db
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

另一个终端执行：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
docker compose ps
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "\dx vector"'
```

/health 返回 HTTP 200 和 {"status":"ok"}，不查询数据库。
本机数据库地址为 127.0.0.1:5433，容器内部端口是 5432。
Compose 使用 PostgreSQL 17 + pgvector 固定标签、命名卷及 pg_isready。
DB_PORT 控制应用连接；Compose 宿主机映射固定为 5433。
数据库具备扩展文件后，仍须运行 Alembic 才能在目标库启用 vector。

## 测试

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m pytest -m integration
```

默认仅运行配置及健康检查测试，不需要数据库。
集成测试显式运行，使用 .env / 环境变量指定的 APP_ENV=local 数据库。
它会执行 upgrade head 并验证迁移版本和 vector；不会清空数据库。
请只配置本地开发数据库。连接失败或配置缺失会使测试失败，不静默跳过。
无独立测试容器、测试业务表或事务回滚 fixture。

## 数据库约定

db/session.py 提供模块级 Engine、async_sessionmaker 和 get_db。
请求通过 Depends(get_db) 获取独立 AsyncSession，关闭时释放会话，
不自动 commit。未来业务显式管理事务；并发任务不得共享会话。
应用 lifespan 退出时 dispose Engine，创建 Engine 不建立连接。
应用启动不迁移，也不调用 create_all。

迁移复用 Settings 与 Base.metadata，以异步连接 run_sync 执行。
初始 upgrade 仅启用 vector，Alembic 自身维护版本表。
downgrade 有意保留共享扩展，不删除未来依赖数据。
当前没有业务模型，未来添加模型时需在迁移环境显式导入。

## 停止与持久化

```powershell
docker compose stop db
```

命名卷会保留数据。已有卷中的账号密码不会随着 .env 修改自动更新，
需要使用原凭据连接后管理数据库账号。不要为解决密码问题随意删除卷。

依赖使用 pyproject.toml 中的兼容范围，通过 venv + pip 安装；没有锁文件，
不同时间解析的补丁版本可能不同。当前 Compose 仅用于本地开发，
POSTGRES_USER 为初始化管理账号；生产权限拆分不在 M1 范围。
