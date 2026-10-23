# 错题帮

面向中学生的个人错题学习系统：uni-app 学生界面，仓颉业务服务与 MySQL，Python 内部算法服务。Python 算法不读写业务数据库。

## 本次提交

在远程精简交付版 f3fdec2 的基础上补齐已在评审程序包中验证的运行改动：

- 支持 xiaojing 的模型配置与 XIAOJING_API_KEY 环境变量读取，实际模型为 gpt-6-luna。
- 服务元信息返回配置中的实际模型名称。
- Excel 导出与前端保持相同的分数公式控制字符修复规则；其他非法控制字符作为输入错误处理。
- 补充对应回归测试及公开部署脚本、依赖清单和部署说明。

评审镜像的源码构建基线为 899b0f60705aafac8ed415ee72278ff1e1559b77；本仓库保留精简版构建与开发入口，不恢复历史文档、视频和测试素材。文档中的 d01d742 为此前文档核对基线；上述改动是后续运行修复。

## 运行方式

已领取评审程序包时，按包内《部署说明.docx》运行 start.sh。运行镜像和模型文件通过评审渠道提供，不存放于此仓库。公开部署资料见 [deployment/competition](deployment/competition/README.md)。

从源码启动时，使用根目录 Makefile 中的 install-cangjie、install、install-browser、mysql、setup-local、dev 与 check 入口。复制 config/api_pool.example.json 为本机 config/api_pool.json，并在运行环境中设置 XIAOJING_API_KEY；也可以写入仅保存在本机的 .env.cangjie。数据库与内部服务配置参照 .env.cangjie.example。默认前端端口为 5175。

AI 请求需要有效密钥、额度和网络；此仓库不提供真实密钥或学生数据。不要将含密钥的评审程序包、.env 或实际 api_pool.json 提交到 Git。

## 本次回归测试

安装算法开发依赖后执行：

```bash
PYTHONPATH=backend-algorithms python -m pytest backend-algorithms/tests -q
```

本目录当前测试覆盖模型配置、环境变量凭据读取和 Excel 控制字符处理；测试通过不代表任意新题均可正确诊断。
