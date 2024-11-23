# 使用官方的 Python 3 镜像作为基础镜像
FROM python:3.12

# 设置工作目录
WORKDIR /app

# 暴露端口 5001 和 5000
EXPOSE 5000 5001

# 默认命令可以是启动应用或空闲状态
CMD ["tail", "-f", "/dev/null"]
