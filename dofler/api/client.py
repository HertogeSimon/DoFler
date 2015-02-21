import urllib2
import time
import os
import json
from requests_futures.sessions import FuturesSession
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dofler.common import md5hash, log
from dofler import config
from dofler.models import *
from dofler.db import SettingSession
from dofler.md5 import md5hash
import bleach

class DoflerClient(object):
    '''
    DoFler API Client Class.  This class handles all client-side API calls to 
    the DoFler service, regardless of the service is remote or local.
    '''
    def __init__(self, host, port, username, password, ssl=False, anon=True):
        self.host = host
        self.port = port
        self.ssl = ssl
        self.anonymize = anon
        self.username = username
        self.opener = FuturesSession(max_workers=10)
        self.login(username, password)
        if self.host in ['localhost', '127.0.0.1']:
            self.engine = create_engine(config.config.get('Database', 'db'), echo=False)
            self.Session = sessionmaker(bind=self.engine)


    def call(self, url, data, files={}):
        '''
        This is the core function that calls the API.  all API calls route
        through here.

        :param url: URL of Call
        :param data: Data to be sent with call

        :type url: str 
        :type data: dictionary, str 

        :return: urllib2 Response Object
        '''
        ssl = {
            True: 'https://',
            False: 'http://'
        }
        location = '%s%s:%s%s' % (ssl[self.ssl], self.host, self.port, url)
        log.debug('CLIENT: %s' % location)
        return self.opener.post(location, data=data, files=files)


    def login(self, username, password):
        '''
        Login Function.

        :param username: username/sensorname
        :param password: username/sensorname password

        :type username: str
        :type password: str

        :return: None
        '''
        self.call('/post/login', {
            'username': username,
            'password': password
        }).result()


    def account(self, username, password, info, proto, parser):
        '''
        Account API call.  This function handles adding accounts into the
        database.

        :param username: Account Username
        :param password: Account Password
        :param info: General Information Field
        :param proto: Discovered Protocol
        :param parser: Parser/Agent to discovere account 

        :type username: str 
        :type password: str 
        :type info: str 
        :type proto: str 
        :type parser: str

        :return: None
        '''
        # If the anonymization bit is set, then we need to hide the password. 
        # We will still display the first 3 characters, however will asterisk
        # the rest of the password past that point.
        if self.anonymize:
            if len(password) >= 3:
                password = '%s%s' % (password[:3], '*' * (len(password) - 3))
        if self.host in ['localhost', '127.0.0.1']:
            s = self.Session()
            if s.query(Account).filter_by(username=bleach.clean(username))\
                               .filter_by(password=bleach.clean(password))\
                               .filter_by(info=bleach.clean(info)).count() < 1 and password != '':
                s.add(Account(bleach.clean(username), 
                              bleach.clean(password), 
                              bleach.clean(info), 
                              bleach.clean(proto), 
                              bleach.clean(parser)
                    )
                )
                s.commit()
                log.debug('DATABASE: Added Account: %s:%s:%s:%s:%s' %\
                          (username, password, info, proto, parser))
        else:
            self.call('/post/account', {
                'username': username,
                'password': password,
                'info': info,
                'proto': proto,
                'parser': parser,
            })


    def image(self, filename):
        '''
        Image API Call.  Uploads the image into the database.

        :param fobj: File-like object with the image contents
        :param filename: Filename or extension of the file. 

        :type fobj: fileobject
        :type filename: str 

        :return: None
        '''
        if os.path.exists(filename):
            if self.host in ['localhost', '127.0.0.1']:
                with open(filename, 'rb') as imagefile:
                    data = imagefile.read()
                md5 = md5hash(data)
                s = self.Session()
                if s.query(Image).filter_by(md5sum=md5).count() > 0:
                    image = s.query(Image).filter_by(md5sum=md5).one()
                    image.timestamp = int(time.time())
                    image.count += 1
                    s.merge(image)
                    log.debug('DATABASE: Updated Image %s' % image.md5sum)
                else:
                    ftype = filename.split('.')[-1]
                    image = Image(int(time.time()), ftype, data, md5)
                    s.add(image)
                    log.debug('DATABASE: Added Image %s' % image.md5sum)
                s.commit()
                s.close()
            else:
                try:
                    self.call('/post/image', {'filetype': filename.split('.')[-1]},
                                             {'file': open(filename, 'rb')})
                except:
                    log.error('API: Upload Failed. %s=%skb' % (filename, 
                                                os.path.getsize(filename) / 1024))
        else:
            log.error('API: %s doesnt exist' % filename)


    def stat(self, proto, count):
        '''
        Statistical API call.  Sends the 1 minute count of packets for a given
        protocol to the backend database.

        :param proto: Protocol name
        :param count: Packet count

        :type proto: str 
        :type count: int 

        :return: None
        '''
        if self.host in ['localhost', '127.0.0.1']:
            s = self.Session()
            s.add(Stat(proto, self.username, count))
            s.commit()
            s.close()
            log.debug('DATABASE: Added Stat %s:%s:%s' % (proto, count, self.username))
        else:
            self.call('/post/stat', {
                'proto': proto, 
                'count': count, 
                'username': self.username
            })


    def reset(self, env):
        '''
        Reset API call.  Sends a reset code to the API for the given type of
        data. 

        :param env: Environment Type.  Valid types are: images, accounts
        :type env: str 
        :return: None 
        '''
        self.call('/post/reset', {'type': env})


    def services(self):
        '''
        Gets the current service statuses. 
        '''
        return json.loads(self.call('/post/services', {
                'action': 'none',
                'parser': 'none',
        }).result().content)


    def start(self, name):
        '''
        Starts the defined service. 
        '''
        return json.loads(self.call('/post/services', {
                'action': 'Start', 
                'parser': name
        }).result().content)


    def stop(self, name):
        '''
        Stops the defined service. 
        '''
        return json.loads(self.call('/post/services', {
            'action': 'Stop', 
            'parser': name
        }).result().content)
