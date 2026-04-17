"""Medu-SPAgent 论文级分析库。

设计为离线运行：
- 连接到平台运行时所用的 Postgres
- 拉取 users / training_sessions / messages / final_evaluations / evaluation_snapshots /
  ct_steps / survey_responses / prompts 全表
- 推导每个学生 / 每节会话 / 每次考试的宽表
- 跑 SP-Agent 三组对照（MA / SA / CT）+ 2 次学习 + 1 次考试 设计的全套描述统计、
  组间多重比较、效应量、重复测量与混合效应、问卷信效度、checklist 逐项 χ²、相关矩阵
- 全部结果在命令行打印（Rich tables）并落到 ``output/`` 目录的 CSV / JSON

使用：
    python -m evaluate run                 # 跑全部分析
    python -m evaluate run --section exam  # 仅跑指定模块
    python -m evaluate dump                # 仅把数据库快照成 CSV
"""

__version__ = "0.1.0"
