#!/usr/bin/env python

import os
import logging
import signal

import requests
from twython import Twython, TwythonStreamer

HASHTAGS = os.environ.get('FGABOT_HASHTAGS',
                          'ccf5352d004e411a8c45e4079f90a0c3').split(',')

ADVICE_BACKEND = os.environ.get(
    'FGABOT_ADVICE_BACKEND', 'http://fuckinggreatadvice.com/advices.json')

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
FONT_PATH = os.path.join(BASE_DIR, 'bnr.ttf')
BG_PATH = os.path.join(BASE_DIR, 'bg.png')


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


class ImageRenderer:
    def __init__(self, convert_path, composite_path, background_path,
                 font_path, output_dir='/tmp'):

        caption_path = os.path.join(output_dir, 'caption.png')

        self.convert_cmd = ('%s -font %s -background transparent -fill white '
                            '-size 900x400 caption:"{}" %s') % (convert_path,
                                                                font_path,
                                                                caption_path)

        self.image_path = os.path.join(output_dir, 'image.png')

        self.composite_cmd = '{} -geometry +20+20 {} {} {}'.format(
            composite_path, caption_path, background_path, self.image_path)

    def render(self, text):
        os.system(self.convert_cmd.format(text))
        os.system(self.composite_cmd)
        return self.image_path


class Bot(TwythonStreamer):

    def __init__(self, twitter_credentials, hashtags, advice_backend,
                 image_renderer, logger):

        self.hashtags = hashtags
        self.advice_backend = advice_backend
        self.image_renderer = image_renderer
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
            advice = self.get_advice()
            image_path = self.image_renderer.render(advice)
            self.logger.debug('user: "%s" advice: %s', name, advice)

            with open(image_path, 'rb') as image:
                response = self.twitter.upload_media(media=image)

                self.twitter.update_status(status='@{}'.format(name),
                                           media_ids=[response['media_id']])
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

    convert_path = os.environ.get('FGABOT_CONVERT_PATH', '/usr/bin/convert')
    composite_path = os.environ.get('FGABOT_COMPOSITE_PATH',
                                    '/usr/bin/composite')

    renderer = ImageRenderer(convert_path, composite_path, BG_PATH, FONT_PATH)
    bot = Bot(twitter_credentials, HASHTAGS, ADVICE_BACKEND, renderer, logger)

    shutdown = make_term_handler(bot, logging)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        logging.debug('running bot')
        bot.run()
    except KeyboardInterrupt:
        shutdown()


if __name__ == "__main__":
    main()
