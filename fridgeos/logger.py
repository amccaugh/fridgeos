import logging
import sys
import os

class FridgeLogger:
    def __init__(self, log_path, debug=False, logger_name='HAL'):
        self.logger = self.setup_logging(log_path, debug, logger_name)

    def setup_logging(self, log_path, debug=False, logger_name='HAL'):
        # Make the logging path if doesn't exist
        if log_path is not None:
            log_dir = os.path.dirname(log_path)
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
        # Create the logger
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)
        # Create 3 "handlers" two which output to a log file, the other to stdout
        handler1 = logging.StreamHandler(sys.stdout)
        handler2 = logging.FileHandler(os.path.join(log_path, f'{logger_name.lower()}-errors.log'), mode='a')
        handler3 = logging.FileHandler(os.path.join(log_path, f'{logger_name.lower()}-debug.log'), mode='a')
        handler1.setLevel(logging.INFO)
        handler2.setLevel(logging.INFO)
        handler3.setLevel(logging.DEBUG)
        # Set the format of the log messages
        log_date_format = '%Y-%m-%d %H:%M:%S'
        format = logging.Formatter(fmt = '%(asctime)s.%(msecs)03d,\t%(levelname)s,\t%(message)s', datefmt=log_date_format)
        handler1.setFormatter(format)
        handler2.setFormatter(format)
        handler3.setFormatter(format)
        # Create the logger
        logger.addHandler(handler1)
        if log_path is not None:
            logger.addHandler(handler2)
            if debug is True:
                logger.addHandler(handler3)
        logger.debug('Starting up server')
        return logger

    def get_logger(self):
        return self.logger 