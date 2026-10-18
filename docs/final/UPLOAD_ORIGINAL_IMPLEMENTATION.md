# 上传原件保留与原图查看

本批修复实际图片核验发现的问题：旧录入接口先normalize，再把JPEG作为original保存，未单独保留上传文件。现在同时保存原始上传字节和标准化处理副本，裁剪、清洁与识别继续使用副本。

## 资源合同

| 资源类型 | 内容与用途 |
| --- | --- |
| `uploaded_original` | 通过图片校验后的原始上传字节；独立路径、SHA-256和签名下载URL |
| `original` | 既有标准化JPEG预览/处理副本；保留原字段和路径合同，供既有裁剪/识别使用 |
| `crop`、`clean`等 | 独立派生资源；均不写入上传原件路径 |

原件文件名由实际字节签名决定，不采用用户提供的文件名或声明的MIME。PNG/JPEG/WebP保存对应后缀；其他经normalize接受的格式也保留原始字节，无法识别的类型以bin保存，不能当作浏览器图片强行预览。normalize仍负责真实图片校验，不把任意上传内容当图片入库。

两个文件和元数据由同一次录入管理：先写独立文件，再以同一MySQL事务写题目/资源/任务；存储或事务失败时清理本次两份文件，不遗留单边资源。复用现有资源表，无新增迁移。

旧题只有标准化JPEG时继续保留，不把旧JPEG冒充恢复出的上传字节，也不补造`uploaded_original`记录。以后新上传才有可核验的上传原件。

## 页面行为

详情“查看原图”优先选择可预览的`uploaded_original`；旧题选择完整original副本，再回退到crop。修复了之前crop优先、原图按钮实际打开裁剪图的问题。无法在浏览器直接预览的上传格式仍有原件下载资源，页面使用标准化预览；原件不混入图片轮播导致打不开。

没有新增说明墙或多个入口，学生仍只需点击原有“查看原图”。其他题干、作答、学习和记录流程保持原合同。

## 本批证据

- 专项`CANGJIE_VERIFY_FOCUS=original-upload make verify-cangjie`已退出0：86项算法、31组仓颉原生，真实HTTP/MySQL验证PNG、带EXIF的JPEG、WebP逐字节保存、文件类型、签名下载、错误文件名/MIME及两文件事务回滚。
- 前端120项/33文件与类型检查通过。新增原图选择测试覆盖有原件、旧题、裁剪图和不能预览的文件；浏览器新增真实PNG上传、签名下载字节比较和原图入口场景。
- 实际服务重启为修复版本，`make check-final`四项通过。`scripts/check_live_image.py`通过现有模型池处理固定生成图片，任务completed、题干包含原方程，`uploaded_original`下载字节、SHA-256、image/png均正确；处理副本路径不同。本地报告`.runtime/live-image-check.json`明确passed=true，未提交账号凭据或报告私有内容。

实际核验命令：先按[实际运行说明](ACTUAL_RUNTIME_IMPLEMENTATION.md)准备本地核验账号，再加载`.env.cangjie`并运行`.venv/bin/python scripts/check_live_image.py`。此命令会创建一条专用核验题并进行实际模型请求；它证明固定图片流程，不代表所有照片和学科的识别质量。

完整`make verify-final`已退出0：120项前端、86项算法、31组仓颉原生、完整HTTP/MySQL及30项浏览器通过（0跳过），包含新增原图页面场景。日志`/tmp/zhiwei-original-final.log`，结果同时记录在[实施进度](IMPLEMENTATION_STATUS.md)。下一步继续处理实际题库、检索/语音和其他页面，不因本项通过宣称整个系统已最终完成。
