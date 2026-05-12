# 导入Python标准库中的日志模块，提供日志记录功能
import logging
# 从自定义模块path_tool中导入获取绝对路径的函数
from .path_tool import get_abs_path
# 导入操作系统接口模块，用于文件和目录操作
import os
# 导入日期时间模块，用于获取当前时间
from datetime import datetime


LOG_ROOT = get_abs_path("logs")
# 确保日志目录存在，如果不存在则创建，exist_ok=True表示目录已存在时不报错
os.makedirs(LOG_ROOT, exist_ok=True)


logging.formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
)

def get_logger(
        # 日志器名称，默认为"agent"
        name: str = "agent",
        # 控制台日志级别，默认为INFO（显示INFO及以上级别的日志）
        integer_level : int = logging.INFO,
        # 文件日志级别，默认为DEBUG（记录所有级别的日志）
        file_level: int = logging.DEBUG,
        # 日志文件路径，默认为None（自动生成）
        log_file = None,
) -> logging.Logger:
    # 根据名称获取或创建一个日志器对象
    logger = logging.getLogger(name)
    # 设置日志器的最低级别为DEBUG，确保能接收所有级别的日志
    logger.setLevel(logging.DEBUG)
    if logger.handlers:
        # 如果已有Handler，直接返回该日志器
        return logger
    # 创建控制台输出Handler，用于将日志输出到终端
    console_handler = logging.StreamHandler()
    console_handler.setLevel(integer_level)
    console_handler.setFormatter(logging.formatter)
    logger.addHandler(console_handler)

    if not log_file:
        # 如果未提供，则自动生成日志文件路径
        # 路径格式：LOG_ROOT/日志器名称_年月日.log
        # 例如：logs/agent_20260405.log
        log_file = os.path.join(LOG_ROOT, f"{name}_{datetime.now().strftime('%Y%m%d')}.log")

    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(file_level)
    file_handler.setFormatter(logging.formatter)
    logger.addHandler(file_handler)

    return logger

logger = get_logger()





