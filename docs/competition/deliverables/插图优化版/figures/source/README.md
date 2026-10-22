# 图形源文件

上一级目录包含10张SVG和对应3000×2000 PNG。SVG中的文字、几何形状、连接线和图标可分别编辑。

`draw_figures.py`为重现入口；运行环境使用Python、Pillow、lxml、CairoSVG及Noto Sans CJK字体。脚本读取同目录`icons/`，输出到上一级`figures/`。字体路径在脚本FONT变量中指定；迁移机器时可调整字体文件位置。字体文件不随交付包分发。

Lucide图标来自官方仓库，许可全文位于`icons/LICENSE`。生成过程未调用图像生成模型；采用本轮要求的可复现SVG绘制方式。图标是原生矢量图元，不影响SVG离线打开。
