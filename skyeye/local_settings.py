# Local settings for development environment
# This file should only contain development-specific overrides
# All sensitive configuration should be in .env file

# Development logging overrides
if 'LOGGING' in globals():
    LOGGING.setdefault('loggers', {})
    LOGGING['loggers']['apps.cmc_proxy'] = {
        'handlers': ['console'],
        'level': 'DEBUG',
        'propagate': False
    }

# Development-specific settings can go here
# For example:
# - Additional debugging tools
# - Development middleware
# - Test database overrides