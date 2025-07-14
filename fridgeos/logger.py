import logging
import logging.handlers
import sys
import os

class FridgeLogger:
    def __init__(self, log_path, debug=False, logger_name='HAL'):
        self.logger = self.setup_logging(log_path, debug, logger_name)

    def setup_logging(self, log_path, debug=False, logger_name='HAL'):
        if log_path is not None:
            log_dir = os.path.dirname(log_path)
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)

        # Use RotatingFileHandler for log rotation
        max_bytes = 10 * 1024 * 1024  # 10 MB
        backup_count = 5  # Number of backup files to keep

        handler1 = logging.StreamHandler(sys.stdout)
        handler2 = logging.handlers.RotatingFileHandler(
            os.path.join(log_path, f'{logger_name.lower()}-errors.log'),
            mode='a', maxBytes=max_bytes, backupCount=backup_count
        )
        handler3 = logging.handlers.RotatingFileHandler(
            os.path.join(log_path, f'{logger_name.lower()}-debug.log'),
            mode='a', maxBytes=max_bytes, backupCount=backup_count
        )
        handler1.setLevel(logging.INFO)
        handler2.setLevel(logging.INFO)
        handler3.setLevel(logging.DEBUG)

        log_date_format = '%Y-%m-%d %H:%M:%S'
        format = logging.Formatter(fmt = '%(asctime)s.%(msecs)03d,\t%(levelname)s,\t%(message)s', datefmt=log_date_format)
        handler1.setFormatter(format)
        handler2.setFormatter(format)
        handler3.setFormatter(format)

        logger.addHandler(handler1)
        if log_path is not None:
            logger.addHandler(handler2)
            if debug is True:
                logger.addHandler(handler3)
        logger.debug('Starting up server')
        return logger
