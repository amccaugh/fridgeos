# This file is part of fridgeos
# Copyright (C) 2025 by Adam McCaughan

# cryoheatflow is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


import logging
import logging.handlers
import sys
import os

class FridgeLogger:
    def __init__(self, log_path, logger_name, debug=False):
        self.logger = self.setup_logging(log_path, logger_name, debug)

    def setup_logging(self, log_path, logger_name, debug=False):
        if log_path is not None:
            # Handle relative paths properly
            if os.path.dirname(log_path) == '':
                # If log_path is just a filename or relative path, create the directory
                if not os.path.exists(log_path):
                    os.makedirs(log_path)
            else:
                # If log_path has a directory component, create the parent directory
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
            os.path.join(log_path, f'{logger_name.lower()}-info.log'),
            mode='a', maxBytes=max_bytes, backupCount=backup_count
        )
        handler3 = logging.handlers.RotatingFileHandler(
            os.path.join(log_path, f'{logger_name.lower()}-debug.log'),
            mode='a', maxBytes=max_bytes, backupCount=backup_count
        )
        handler4 = logging.handlers.RotatingFileHandler(
            os.path.join(log_path, f'{logger_name.lower()}-errors.log'),
            mode='a', maxBytes=max_bytes, backupCount=backup_count
        )
        handler1.setLevel(logging.INFO)
        handler2.setLevel(logging.INFO)
        handler3.setLevel(logging.DEBUG)
        handler4.setLevel(logging.ERROR)


        log_date_format = '%Y-%m-%d %H:%M:%S'
        format = logging.Formatter(fmt = '%(asctime)s.%(msecs)03d,\t%(levelname)s,\t%(message)s', datefmt=log_date_format)
        handler1.setFormatter(format)
        handler2.setFormatter(format)
        handler3.setFormatter(format)
        handler4.setFormatter(format)

        logger.addHandler(handler1)
        if log_path is not None:
            logger.addHandler(handler2)
            logger.addHandler(handler4)
            if debug is True:
                logger.addHandler(handler3)
        logger.debug('Starting up server')
        return logger
