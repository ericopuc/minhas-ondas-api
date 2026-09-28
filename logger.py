from logging.config import dictConfig
import logging
import os


log_path = "log/"
# Verifica se o diretorio para armazenar os logs não existe
if not os.path.exists(log_path):
    # então cria o diretorio
    os.makedirs(log_path)


dictConfig({
    "version": 1,
    "disable_existing_loggers": True,
    "formatters": {
        "default": {
            "format": "[%(asctime)s] %(levelname)-4s %(funcName)s() L%(lineno)-4d %(message)s",
        },
        "detailed": {
            "format": "[%(asctime)s] %(levelname)-4s %(funcName)s() L%(lineno)-4d %(message)s - call_trace=%(pathname)s L%(lineno)-4d",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "stream": "ext://sys.stdout",
        },
        "detailed_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "detailed",
            "filename": "log/api.detailed.log",
            "maxBytes": 100000,
            "backupCount": 5,
            "delay": "True",
        }
    },
    "root": {
        "handlers": ["console", "detailed_file"],
        "level": "INFO",
    }
})


logger = logging.getLogger(__name__)
