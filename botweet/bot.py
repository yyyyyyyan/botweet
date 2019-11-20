from .event import BotweetEvent
from mimetypes import guess_extension
from configparser import ConfigParser
from tempfile import TemporaryFile
from shutil import copyfileobj
from urllib.request import urlopen
from threading import current_thread, main_thread
from time import sleep
import tweepy
import os


class Botweet:ss
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
            self._auth = tweepy.OAuthHandler(
                config["CONSUMER_KEY"], config["CONSUMER_SECRET"]
            )
        except KeyError as err:
            raise KeyError(
                "Config missing 'CONSUMER_KEY' and 'CONSUMER_SECRET'"
            ) from err
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
            raise AttributeError(
                "API not yet configured. Call the set_access method to configure it"
            )
        return self._api

    def set_access(self, access_token=None, access_secret=None):
        if access_token and access_secret:
            self._auth.set_access_token(access_token, access_secret)
            self._api = tweepy.API(
                self._auth, wait_on_rate_limit=True, wait_on_rate_limit_notify=True
            )
            self._me = self._api.me()
        else:
            print("Authorize the application in this URL:")
            print(self._auth.get_authorization_url())
            verifier = input("Enter the verifier code: ")
            self.set_access(*self._auth.get_access_token(verifier))

    def _upload_media(self, *medias):
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
        if kwargs.get("reply_to"):
            tweet_info["in_reply_to_status_id"] = kwargs["reply_to"].id
            tweet_info["auto_populate_reply_metadata"] = True
        medias = tweet_info.get("medias")
        if medias:
            if len(medias) > 4:
                raise ValueError("Only 4 medias allowed per tweet")
            tweet_info["media_ids"] = self._upload_media(*medias)
        self._api.update_status(**tweet_info)

    def _message(self, get_message_func, *args, **kwargs):
        message_info = get_message_func(*args, **kwargs)
        media = message_info.get("media")
        if media:
            if not isinstance(media, str):
                raise ValueError("Only 1 media allowed per direct message")
            message_info["attachment_type"] = "media"
            (message_info["attachment_media_id"],) = self._upload_media(media)
        recipient = kwargs.get("recipient")
        if recipient:
            message_info["recipient_id"] = recipient
            self._api.send_direct_message(**message_info)
        else:
            raise ValueError("Message must have recipient")

    def _get_last_id_and_match(self, tweet_id, text, last_id, regex):
        if tweet_id > last_id:
            last_id = tweet_id
        match = True
        if regex:
            match = regex.search(text)
        return last_id, match

    def _get_kwargs(self, options, args, kwargs):
        for key, value in zip(options, args):
            options[key] = value
        options.update(kwargs)
        return options

    def tweet_per_time(self, get_tweet_info, interval, stop_event=None):
        if current_thread() is main_thread():
            return BotweetEvent(self.tweet_per_time, get_tweet_info, interval)
        while not stop_event.is_set():
            self._tweet(get_tweet_info)
            sleep(interval)

    def react_to_tweets_from_api_method(self, api_method, *args, **kwargs):
        if current_thread() is main_thread():
            return BotweetEvent(
                self.react_to_tweets_from_api_method, api_method, *args, **kwargs
            )
        options = {
            "get_tweet_info": None,
            "get_message_info": None,
            "check_interval": 60,
            "regex": None,
            "since_id": 1,
            "retweet": False,
        }
        kwargs = self._get_kwargs(options, args, kwargs)
        get_tweet_info = kwargs.get("get_tweet_info")
        get_message_info = kwargs.get("get_message_info")
        method_parameters = kwargs.get("method_parameters", {})
        method_parameters["since_id"] = options["since_id"]
        while not options["stop_event"].is_set():
            for tweet in tweepy.Cursor(api_method, **method_parameters).items():
                since_id, match = self._get_last_id_and_match(
                    mention.id, mention.text, options["since_id"], kwargs["regex"]
                )
                method_parameters["since_id"] = since_id
                if match:
                    if options["retweet"]:
                        self._api.retweet(tweet.id)
                    if get_tweet_info:
                        self._tweet(get_tweet_info, reply_to=tweet, re_match=match)
                    if get_message_info:
                        self._message(get_message_info, recipient=tweet.user.id)
            sleep(kwargs["check_interval"])

    def react_to_mentions(self, *args, **kwargs):
        args = self._api.mentions_timeline, *args
        return BotweetEvent(self.react_to_tweets_from_api_method, *args, **kwargs)

    def reply_mentions(self, get_tweet_info, *args, **kwargs):
        args = get_tweet_info, *args
        return self.react_to_mentions(*args, **kwargs)

    def retweet_mentions(self, *args, **kwargs):
        kwargs["retweet"] = True
        return self.react_to_mentions(*args, **kwargs)

    def react_to_searches(self, query, search_parameters=None, *args, **kwargs):
        args = self._api.search, *args
        if search_parameters is None:
            search_parameters = {}
        search_parameters["q"] = query
        kwargs["method_parameters"] = search_parameters
        return BotweetEvent(self.react_to_tweets_from_api_method, *args, **kwargs)

    def reply_searches(
        self, get_tweet_info, query, search_parameters=None, *args, **kwargs
    ):
        args = query, search_parameters, get_tweet_info, *args
        return self.react_to_searches(*args, **kwargs)

    def retweet_searches(self, query, search_parameters=None, *args, **kwargs):
        args = query, search_parameters, *args
        kwargs["retweet"] = True
        return self.react_to_searches(*args, **kwargs)

    def react_to_tweets_from_user(self, user, *args, **kwargs):
        args = self._api.mentions_timeline, *args
        kwargs["method_parameters"] = kwargs.get("method_parameters", {})
        kwargs["method_parameters"]["screen_name"] = user
        return BotweetEvent(self.react_to_tweets_from_api_method, *args, **kwargs)

    def reply_tweets_from_user(self, get_tweet_info, user, *args, **kwargs):
        args = user, get_tweet_info, *args
        return self.react_to_tweets_from_user(*args, **kwargs)

    def retweet_tweets_from_user(self, user, *args, **kwargs):
        args = user, *args
        kwargs["retweet"] = True
        return self.react_to_tweets_from_user(*args, **kwargs)

    def react_to_messages(self, *args, **kwargs):
        if current_thread() is main_thread():
            return BotweetEvent(self.react_to_messages, **kwargs)
        options = {
            "get_message_info": None,
            "get_tweet_info": None,
            "check_interval": 60,
            "regex": None,
            "since_id": 1,
        }
        kwargs = self._get_kwargs(options, args, kwargs)
        get_tweet_info = kwargs.get("get_tweet_info")
        get_message_info = kwargs.get("get_message_info")
        while not kwargs["stop_event"].is_set():
            messages = [
                msg
                for msg in self._api.list_direct_messages(count=200)
                if int(msg.id) > kwargs["since_id"]
                and msg.message_create["sender_id"] != self._me.id_str
            ]
            for msg in messages:
                since_id, match = self._get_last_id_and_match(
                    int(msg.id),
                    msg.message_create["message_data"]["text"],
                    kwargs["since_id"],
                    kwargs["regex"],
                )
                kwargs["since_id"] = since_id
                if match:
                    if get_tweet_info:
                        self._tweet(get_tweet_info, msg=msg, re_match=match)
                    if get_message_info:
                        self._message(
                            get_message_info,
                            recipient=int(msg.message_create["sender_id"]),
                        )
            sleep(kwargs["check_interval"])

    def reply_messages(self, get_message_info, *args, **kwargs):
        args = get_message_info, *args
        return self.react_to_tweets_from_user(*args, **kwargs)
