# SPDX-FileCopyrightText: Thamerlan
# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
# from __future__ import absolute_import, division, unicode_literals
import resources.lib.utils as utils
from resources.lib.cron import CronService

# run the program
utils.log("Cron for Kodi service starting....")
CronService().runProgram()
