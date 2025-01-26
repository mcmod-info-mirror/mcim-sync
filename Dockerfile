# 第一阶段：构建阶段
FROM python:3.11-slim-buster AS builder

# 设置工作目录
WORKDIR /app

# 复制依赖文件并安装依赖
COPY requirements.txt .
RUN pip config set global.index-url https://pypi.mirrors.ustc.edu.cn/simple/ \
    && pip install --user --no-cache-dir -r requirements.txt

# 复制应用程序代码
COPY start.py start.py
COPY mcim_sync ./mcim_sync

# 第二阶段：运行阶段
FROM python:3.11-slim-buster

# 设置工作目录
WORKDIR /app

# 复制已安装的依赖
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# 复制应用程序代码
COPY --from=builder /app /app