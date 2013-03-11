#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import argparse
import os
import re
import sys
import urllib
import urllib2
import xml.etree.ElementTree as ET

from xiami_dl import get_downloader

# ID3 tags support depends on Mutagen
try:
    import mutagen
    from mutagen.mp3 import MP3
    from mutagen.id3 import ID3,APIC,error,TIT2,TALB,TPE1,USLT
    from mutagen.easyid3 import EasyID3
except:
    mutagen = None
    print "No mutagen available. ID3 tags won't be written."


VERSION = '0.1.6'

URL_PATTERN_ID = 'http://www.xiami.com/song/playlist/id/%d'
URL_PATTERN_SONG = '%s/object_name/default/object_id/0' % URL_PATTERN_ID
URL_PATTERN_ALBUM = '%s/type/1' % URL_PATTERN_ID
URL_PATTERN_PLAYLIST = '%s/type/3' % URL_PATTERN_ID

HEADERS = {
    'User-Agent':
    'Mozilla/5.0 (compatible; MSIE 9.0; Windows NT 7.1; Trident/5.0)',

    'Referer': 'http://www.xiami.com/song/play'
}


def get_response(url):
    """ Get HTTP response as text

    If sent without the headers, there may be a 503/403 error.
    """
    request = urllib2.Request(url)
    for header in HEADERS:
        request.add_header(header, HEADERS[header])

    try:
        response = urllib2.urlopen(request)
        return response.read()
    except urllib2.URLError as e:
        print e

    return ''


def get_playlist_from_url(url):
    tracks = parse_playlist(get_response(url))
    tracks = [{key: unicode(track[key]) for key in track} for track in tracks]
    return tracks


def parse_playlist(playlist):
    try:
        xml = ET.fromstring(playlist)
    except:
        return []

    return [
        {
            'title': track.find('{http://xspf.org/ns/0/}title').text,
            'location': track.find('{http://xspf.org/ns/0/}location').text,
            'lyric': track.find('{http://xspf.org/ns/0/}lyric').text,
            'pic': track.find('{http://xspf.org/ns/0/}pic').text,
            'artist': track.find('{http://xspf.org/ns/0/}artist').text,
            'album': track.find('{http://xspf.org/ns/0/}album_name').text
        }
        for track in xml.iter('{http://xspf.org/ns/0/}track')
    ]


def decode_location(location):
    url = location[1:]
    urllen = len(url)
    rows = int(location[0:1])

    cols_base = urllen / rows  # basic column count
    rows_ex = urllen % rows    # count of rows that have 1 more column

    matrix = []
    for r in xrange(rows):
        length = cols_base + 1 if r < rows_ex else cols_base
        matrix.append(url[:length])
        url = url[length:]

    url = ''
    for i in xrange(urllen):
        url += matrix[i % rows][i / rows]

    return urllib.unquote(url).replace('^', '0')


def sanitize_filename(filename):
    return re.sub(r'[\\/:*?<>|]', '_', filename)


# Refer: http://code.activestate.com/recipes/577058/
def query_yes_no(question, default="yes"):
    """Ask a yes/no question via raw_input() and return their answer.

    "question" is a string that is presented to the user.
    "default" is the presumed answer if the user just hits <Enter>.
        It must be "yes" (the default), "no" or None (meaning
        an answer is required of the user).

    The "answer" return value is one of "yes" or "no".
    """
    valid = {"yes": "yes", "y": "yes", "ye": "yes",
             "no": "no", "n": "no"}
    if default is None:
        prompt = " [y/n] "
    elif default == "yes":
        prompt = " [Y/n] "
    elif default == "no":
        prompt = " [y/N] "
    else:
        raise ValueError("invalid default answer: '%s'" % default)

    while True:
        sys.stdout.write(question + prompt)
        choice = raw_input().lower()
        if default is not None and choice == '':
            return default
        elif choice in valid.keys():
            return valid[choice]
        else:
            sys.stdout.write("Please respond with 'yes' or 'no' "
                             "(or 'y' or 'n').\n")


def parse_arguments():

    note = 'The following SONG, ALBUM, and PLAYLIST are IDs which can be' \
           'obtained from the URL of corresponding web page.'

    parser = argparse.ArgumentParser(description=note)

    parser.add_argument('-v', '--version', action='version', version=VERSION)
    parser.add_argument('-f', '--force', action='store_true',
                        help='overwrite existing files without prompt')
    parser.add_argument('-t', '--tool', choices=['wget', 'urllib2'],
                        help='change the download tool')
    parser.add_argument('-s', '--song', action='append',
                        help='adds songs for download',
                        type=int, nargs='+')
    parser.add_argument('-a', '--album', action='append',
                        help='adds all songs in the albums for download',
                        type=int, nargs='+')
    parser.add_argument('-p', '--playlist', action='append',
                        help='adds all songs in the playlists for download',
                        type=int, nargs='+')
    parser.add_argument('--no-tag', action='store_true',
                        help='skip adding ID3 tag')

    return parser.parse_args()


class XiamiDownloader:
    def __init__(self):
        self.force_mode = False

    def download(self, url, filename):
        if not self.force_mode and os.path.exists(filename):
            if query_yes_no('File already exists. Skip downloading?') == 'yes':
                return
        self.downloader(url, filename, HEADERS)


def build_url_list(pattern, l):
    return [pattern % item for group in l for item in group]


def add_id3_tag(filename, track):
    print 'Tagging...'

    print 'Getting album cover...'
    image = get_response(track['pic'])
    print 'Getting lyrics...'
    lyric = get_response(track['lyric'])

    musicfile = MP3(filename, ID3=ID3)
    try:
        musicfile.add_tags()
    except error:
        pass

    musicfile.tags.add(
        #Cover img
        APIC(
            encoding=3, #utf-8
            mime='image/jpeg',
            type=3, # is cover
            desc=u'Cover',
            data=image))

    musicfile.tags.add(
        #Title
        TIT2(
            encoding=3,
            text=track['title']
        )
    )
    musicfile.tags.add(
        #Album name
        TALB(
            encoding=3,
            text=track['album']
        )
    )
    musicfile.tags.add(
        #Artist
        TPE1(
            encoding=3,
            text=track['artist']
        )
    )
    musicfile.tags.add(
        USLT(
            encoding=3,
            desc=u'desc',
            text=lyric
        )
    )
    print musicfile.pprint()
    musicfile.save()


if __name__ == '__main__':

    args = parse_arguments()

    xiami = XiamiDownloader()
    xiami.downloader = get_downloader(args.tool)
    xiami.force_mode = args.force

    urls = []

    if args.song:
        urls.extend(build_url_list(URL_PATTERN_SONG, args.song))
    if args.album:
        urls.extend(build_url_list(URL_PATTERN_ALBUM, args.album))
    if args.playlist:
        urls.extend(build_url_list(URL_PATTERN_PLAYLIST, args.playlist))

    # parse playlist xml for a list of track info
    tracks = []
    for playlist_url in urls:
        for url in get_playlist_from_url(playlist_url):
            tracks.append(url)

    print '%d file(s) to download' % len(tracks)

    for i in xrange(len(tracks)):
        track = tracks[i]
        track['url'] = decode_location(track['location'])

    for i in xrange(len(tracks)):
        track = tracks[i]
        filename ='%s.mp3' % sanitize_filename(track['title'])
        url = track['url']
        print '\n[%d/%d] %s' % (i + 1, len(tracks), filename)
        xiami.download(url, filename)

        if mutagen and (not args.no_tag):
            add_id3_tag(filename, track)
