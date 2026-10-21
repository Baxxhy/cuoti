# 快速运行

项目根目录执行`make install`、`make install-cangjie`，启动本地MySQL后使用现有`.env.cangjie`运行`make dev`。仅全新环境可运行`make setup-local`，它不会覆盖已有库和配置。完整命令及依赖见根目录README。

API池已从旧后端目录迁到`config/api_pool.json`；如使用`CANGJIE_API_POOL_PATH`，同步设置该路径。配置不提交Git，不向前端暴露。

检查服务用`make check`；前端单测用`make test-frontend`，算法用`make test-algorithms`，完整验收用`make verify`。App生产构建需要前端配置实际可访问的HTTPS API地址，本地资源构建不产生签名安装包。
