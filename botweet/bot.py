from event import BotweetEvent
from configparser import ConfigParser
from threading import Thread
from time import sleep
import tweepy
import os


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
            self._auth = tweepy.OAuthHandler(config["CONSUMER_KEY"], config["CONSUMER_SECRET"])
        except KeyError as err:
            raise KeyError("Config missing 'CONSUMER_KEY' and 'CONSUMER_SECRET'") from err
        else:
            access_token = config.get("ACCESS_TOKEN")
            access_secret = config.get("ACCESS_SECRET")
            if access_token and access_secret:
                self.set_access(access_token, access_secret)
            else:
                self._api = None

    @property
    def auth(self):
        return self._auth

    @property
    def api(self):
        if self._api is None:
            raise AttributeError("API not yet configured. Call the set_access method to configure it")
        return self._api

    def set_access(self, access_token, access_secret):
        self._auth.set_access_token(access_token, access_secret)
        self._api = tweepy.API(self._auth)

    def stop_event(self, event):
        if event.is_set():
            print('Event is already stopped')
        else:
            event.set()

    def _tweet_per_time(self, get_tweet_func, interval, stop_event):
        while not stop_event.is_set():
            tweet_info = get_tweet_func()
            if tweet_info.get("filename"):
                self._api.update_with_media(**tweet_info)
            else:
                self._api.update_status(**tweet_info)
            sleep(interval)

    def tpt(self, get_tweet_func, interval):
        botweet_event = BotweetEvent()
        thread = Thread(target=self._tweet_per_time, args=(get_tweet_func, interval, botweet_event))
        thread.start()
        return botweet_event
