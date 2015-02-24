__version__ = '0.4.2.2'
__author__ = 'Steven McGrath <steve@chigeek.com>'
__website__ = 'http://chigeek.com/tag/dofler.html'
__repository__ = 'https://github.com/SteveMcGrath/DoFler'

def get_version_info():
    return {
        'version': __version__,
        'author': __author__,
        'website': __website__,
        'repository': __repository__,
    }

import sys
reload(sys)
sys.setdefaultencoding('utf-8')

import db
import api
import parsers
import md5
import common
import models
import monitor
import cli
import svc
import report