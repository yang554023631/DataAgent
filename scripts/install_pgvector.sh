#!/bin/bash
set -e

INSTALL_DIR="$HOME/Tools/pgsql"
DATA_DIR="$HOME/Tools/pgsql/data"
PG_VERSION="16.2"
PGVECTOR_VERSION="0.7.0"

echo "=== 安装 PostgreSQL $PG_VERSION + pgvector $PGVECTOR_VERSION ==="
echo "安装目录: $INSTALL_DIR"
echo "数据目录: $DATA_DIR"

# 创建目录
mkdir -p "$INSTALL_DIR"
mkdir -p "$DATA_DIR"

# 下载 PostgreSQL
cd /tmp
if [ ! -f "postgresql-$PG_VERSION.tar.gz" ]; then
    echo "下载 PostgreSQL..."
    curl -O "https://ftp.postgresql.org/pub/source/v$PG_VERSION/postgresql-$PG_VERSION.tar.gz"
fi

# 解压编译 PostgreSQL
echo "编译 PostgreSQL..."
tar -xzf "postgresql-$PG_VERSION.tar.gz"
cd "postgresql-$PG_VERSION"
./configure --prefix="$INSTALL_DIR" --without-readline --without-zlib
make -j$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)
make install

# 配置环境变量
export PATH="$INSTALL_DIR/bin:$PATH"
export PGDATA="$DATA_DIR"

# 初始化数据库
echo "初始化数据库..."
initdb -D "$DATA_DIR"

# 启动 PostgreSQL
echo "启动 PostgreSQL..."
pg_ctl -D "$DATA_DIR" -l "$DATA_DIR/postgresql.log" start

# 等待启动
sleep 3

# 创建默认数据库
createdb postgres || true

# 下载编译 pgvector
echo "安装 pgvector..."
cd /tmp
if [ ! -f "v$PGVECTOR_VERSION.tar.gz" ]; then
    curl -L -O "https://github.com/pgvector/pgvector/archive/refs/tags/v$PGVECTOR_VERSION.tar.gz"
fi
tar -xzf "v$PGVECTOR_VERSION.tar.gz"
cd "pgvector-$PGVECTOR_VERSION"
make
make install

# 创建扩展
psql -d postgres -c "CREATE EXTENSION IF NOT EXISTS vector;"

echo ""
echo "=== 安装完成 ==="
echo "PostgreSQL 安装在: $INSTALL_DIR"
echo "数据目录: $DATA_DIR"
echo "端口: 5432"
echo ""
echo "请将以下内容添加到 ~/.bashrc 或 ~/.zshrc:"
echo "export PATH=\"$INSTALL_DIR/bin:\$PATH\""
echo "export PGDATA=\"$DATA_DIR\""
echo ""
echo "启动命令: pg_ctl start"
echo "停止命令: pg_ctl stop"
