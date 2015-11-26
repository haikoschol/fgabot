#!/usr/bin/env python

import os
import logging
import signal

import requests
from twython import Twython, TwythonStreamer

HASHTAGS = os.environ.get('FGABOT_HASHTAGS',
                          'ccf5352d004e411a8c45e4079f90a0c3').split(',')

ADVICE_BACKEND = os.environ.get(
    'FGABOT_ADVICE_BACKEND',
    'https://goodfuckingadvice.herokuapp.com/advices.json')


class TwitterCredentials:
    @classmethod
    def from_env(cls):
        key = os.environ['FGABOT_API_KEY']
        secret = os.environ['FGABOT_API_SECRET']
        token = os.environ['FGABOT_OAUTH_TOKEN']
        token_secret = os.environ['FGABOT_OAUTH_TOKEN_SECRET']
        return TwitterCredentials(key, secret, token, token_secret)

    def __init__(self, api_key, api_secret, oauth_token, oauth_token_secret):
        self.api_key = api_key
        self.api_secret = api_secret
        self.oauth_token = oauth_token
        self.oauth_token_secret = oauth_token_secret

    def as_list(self):
        return [self.api_key, self.api_secret, self.oauth_token,
                self.oauth_token_secret]


class Bot(TwythonStreamer):
    def __init__(self, twitter_credentials, hashtags, advice_backend, logger):
        self.hashtags = hashtags
        self.advice_backend = advice_backend
        self.logger = logger
        super().__init__(*twitter_credentials.as_list())
        self.twitter = Twython(*twitter_credentials.as_list())

    def get_advice(self):
        response = requests.get(self.advice_backend)
        response.raise_for_status()
        return response.json()['content']

    def on_error(self, status_code, data):
        self.logger.error('[%i] %s', status_code, data)

    def on_success(self, data):
        try:
            name = data['user']['screen_name']
            tweet = '@{} {}'.format(name, self.get_advice())
            self.logger.debug('sending tweet: "%s"', tweet)
            self.twitter.update_status(status=tweet)
        except Exception as e:
            self.logger.exception(data)

    def run(self):
        phrases = ','.join(['#{}'.format(t) for t in self.hashtags])
        self.statuses.filter(track=phrases)


def make_term_handler(bot, logger):
    def shutdown(*args):
        logger.debug('stopping bot')
        bot.disconnect()

    return shutdown


def main():
    twitter_credentials = TwitterCredentials.from_env()
    lvl = os.environ.get('FGABOT_LOGLEVEL', 'WARNING').upper()
    fmt = '[%(asctime)s] %(name)s %(levelname)s %(message)s'
    logging.basicConfig(format=fmt, level=lvl)
    logger = logging.getLogger('FGAbot')
    bot = Bot(twitter_credentials, HASHTAGS, ADVICE_BACKEND, logger)

    shutdown = make_term_handler(bot, logging)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        logging.debug('running bot')
        bot.run()
    except KeyboardInterrupt:
        shutdown()


if __name__ == "__main__":
    main()
