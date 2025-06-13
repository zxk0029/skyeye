from __future__ import absolute_import, unicode_literals

# 确保在Django启动时，app已经被导入
from .celery import app as celery_app

__all__ = ('celery_app',)
