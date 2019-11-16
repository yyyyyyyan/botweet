from .event import BotweetEvent
from mimetypes import guess_extension
from configparser import ConfigParser
from tempfile import TemporaryFile
from shutil import copyfileobj
from urllib.request import urlopen
from threading import Thread, current_thread, main_thread
from time import sleep
import tweepy
import os


class Botweet:
    def __init__(self, config_dict=None, config_file=None):
        if config_dict:
            config = config_dict
        elif config_file:
            config_parser = ConfigParser()
            config_parser.read(config_file)
            config = config_parser["TWITTER"]
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

    def set_access(self, access_token=None, access_secret=None):
        if access_token and access_secret:
            self._auth.set_access_token(access_token, access_secret)
            self._api = tweepy.API(self._auth)
        else:
            print("Authorize the application in this URL:")
            print(self._auth.get_authorization_url())
            verifier = input("Enter the verifier code: ")
            self.set_access(*self._auth.get_access_token(verifier))

    def stop_event(self, event):
        if event.is_set():
            print("Event is already stopped")
        else:
            event.set()

    def _start_event(self, func, *args, **kwargs):
        stop_event = BotweetEvent()
        args += (stop_event,)
        thread = Thread(target=func, args=args, kwargs=kwargs)
        thread.start()
        return stop_event

    def _upload_medias(self, medias):
        if len(medias) > 4:
            raise ValueError("Only 4 medias allowed per tweet")
        media_ids = []
        for media in medias:
            if os.path.isfile(media):
                twitter_media = self._api.media_upload(media)
            else:
                response = urlopen(media)
                response_info = response.info()
                filename = "img" + guess_extension(response_info.get_content_type())
                with TemporaryFile() as tmp:
                    copyfileobj(response, tmp)
                    twitter_media = self._api.media_upload(filename, file=tmp)
            media_ids.append(twitter_media.media_id)
        return media_ids

    def _tweet(self, get_tweet_func, *args, **kwargs):
        tweet_info = get_tweet_func(*args, **kwargs)
        if kwargs.get("status"):
            tweet_info["in_reply_to_status_id"] = kwargs["status"].id
            tweet_info["auto_populate_reply_metadata"] = True
        if tweet_info.get("medias"):
            tweet_info["media_ids"] = self._upload_medias(tweet_info["medias"])
        self._api.update_status(**tweet_info)

    def _get_last_id_and_match(self, tweet_id, text, last_id, regex):
        if tweet_id > last_id:
            last_id = tweet_id
        match = True
        if regex:
            match = regex.search(text)
        return last_id, match

    def tweet_per_time(self, get_tweet_func, interval, stop_event=None):
        if current_thread() is main_thread():
            return self._start_event(self.tweet_per_time, get_tweet_func, interval)
        while not stop_event.is_set():
            self._tweet(get_tweet_func)
            sleep(interval)

    def _tweet_interact_mentions(self, *args):
        get_tweet_func, retweet, check_interval, regex, since_id, stop_event = args
        while not stop_event.is_set():
            for mention in tweepy.Cursor(self._api.mentions_timeline, since_id=since_id).items():
                since_id, match = self._get_last_id_and_match(mention.id, mention.text, since_id, regex)
                if match:
                    if retweet:
                        self._api.retweet(mention.id)
                    else:
                        self._tweet(get_tweet_func, status=mention, re_match=match)
            sleep(check_interval)

    def tweet_reply_mentions(self, get_tweet_func, check_interval=60, regex=None, since_id=1):
        return self._start_event(self._tweet_interact_mentions, get_tweet_func, False, check_interval, regex, since_id)

    def tweet_retweet_mentions(self, check_interval=60, regex=None, since_id=1):
        return self._start_event(self._tweet_interact_mentions, None, True, check_interval, regex, since_id)

    def tweet_reply_messages(self, get_tweet_func, check_interval=60, regex=None, since_id=1, stop_event=None):
        if current_thread() is main_thread():
            return self._start_event(self.tweet_reply_messages, get_tweet_func, check_interval, regex, since_id)
        while not stop_event.is_set():
            messages = [msg for msg in self._api.list_direct_messages() if int(msg.id) > since_id]
            for msg in messages:
                since_id, match = self._get_last_id_and_match(int(msg.id), msg.message_create['message_data']['text'], since_id, regex)
                if match:
                    self._tweet(get_tweet_func, msg=msg, re_match=match)
            sleep(check_interval)

    def _tweet_interact_searches(self, *args, **search_parameters):
        get_tweet_func, query, retweet, check_interval, regex, since_id, count, stop_event = args
        while not stop_event.is_set():
            search_parameters['q'] = query
            for result in tweepy.Cursor(self._api.search, **search_parameters).items(count):
                since_id, match = self._get_last_id_and_match(result.id, result.text, since_id, regex)
                if match:
                    if retweet:
                        self._api.retweet(result.id)
                    else:
                        self._tweet(get_tweet_func, status=result, re_match=match)
            sleep(check_interval)

    def tweet_reply_searches(self, get_tweet_func, query, check_interval=60, regex=None, since_id=1, count=200, **search_parameters):
        return self._start_event(self._tweet_interact_searches, get_tweet_func, query, False, check_interval, regex, since_id, count, **search_parameters)

    def tweet_retweet_searches(self, query, check_interval=60, regex=None, since_id=1, count=200, **search_parameters):
        return self._start_event(self._tweet_interact_searches, None, query, True, check_interval, regex, since_id, count, **search_parameters)