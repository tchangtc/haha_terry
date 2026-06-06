# Terry — containerd 部署指南

## containerd 是什么？

containerd 是 CNCF 毕业的工业级容器运行时，Docker 和 Kubernetes 的底层都使用它。相比 Docker，containerd 更轻量、启动更快、资源占用更少。

## 三种部署方式

### 方式一：nerdctl（推荐，Docker 兼容）

```bash
# 安装 nerdctl（Docker 兼容 CLI for containerd）
# macOS:  brew install nerdctl
# Linux:  wget https://github.com/containerd/nerdctl/releases/latest/download/nerdctl-full-$(uname -m).tar.gz

# 构建镜像
nerdctl build -t terry:latest .

# 启动
nerdctl compose -f deploy/containerd/docker-compose.yml up

# 或直接运行
nerdctl run -it --rm \
  -v $(pwd):/app \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  terry:latest
```

### 方式二：Kubernetes（生产环境）

```bash
# 编辑密钥（替换 API key）
kubectl apply -f deploy/kubernetes/terry.yaml

# 查看状态
kubectl get pods -n terry

# 进入交互模式
kubectl exec -it -n terry deploy/terry-agent -- python -m terry.cli

# 访问 WebUI（端口转发）
kubectl port-forward -n terry svc/terry-webui 8670:8670
# 浏览器打开 http://localhost:8670
```

### 方式三：原生 ctr（最底层）

```bash
# 1. 先用 Docker/buildah 构建镜像
docker build -t terry:latest .

# 2. 导出并导入到 containerd
docker save terry:latest | ctr image import -

# 3. 运行
ctr run --rm -t \
  --mount type=bind,src=$(pwd),dst=/app,options=rbind:rw \
  --env ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  docker.io/library/terry:latest terry-agent
```

## Docker vs containerd 对比

| | Docker | containerd + nerdctl | containerd + k8s |
|--|--------|---------------------|-------------------|
| 镜像构建 | `docker build` | `nerdctl build` | 需外部构建 |
| 服务编排 | `docker compose` | `nerdctl compose` | `kubectl apply` |
| 资源占用 | ~500MB+ | ~200MB | 按需 |
| 适用场景 | 开发/测试 | 单机生产 | 集群生产 |
| 学习曲线 | 低 | 低（兼容 Docker） | 中 |
