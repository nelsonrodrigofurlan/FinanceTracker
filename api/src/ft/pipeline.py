"""Entrypoint do Cloud Run Job diário (coleta → scanner → alertas).

F0: apenas valida que o Job executa. As etapas reais entram na F2/F5/F6.
"""

import logging
import sys

from ft import __version__
from ft.config import get_settings

logger = logging.getLogger("ft.pipeline")


def run() -> int:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    logger.info("pipeline start version=%s env=%s", __version__, settings.app_env)
    logger.info("pipeline finished: no steps configured yet (F0)")
    return 0


if __name__ == "__main__":
    sys.exit(run())
