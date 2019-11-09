import os
from configparser import ConfigParser

import tweepy

class Botweet:
    def __init__(self, config_dict=None, config_file=None):
        if config_dict:
            config = config_dict
        elif config_file:
            config = ConfigParser()
            config.read(config_file)
        else:
            config = os.environ

        try:
            self.auth = tweepy.OAuthHandler(config['CONSUMER_KEY'], config['CONSUMER_SECRET'])
        except KeyError as err:
            raise KeyError('Config missing "CONSUMER_KEY" and "CONSUMER_SECRET"') from err
        else:
            access_token = config.get('ACCESS_TOKEN')
            access_secret = config.get('ACCESS_SECRET')
            if access_token and access_secret:
                self.auth.set_access_token(access_token, access_secret)
                self.api = tweepy.API(self.auth)

