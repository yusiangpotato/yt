from __future__ import print_function

import curses
import curses.textpad
import curses.wrapper
import json
import locale
import re
import subprocess
import sys
import urllib
import urllib2
import argparse
import time

import os

# Define possible player modes.
MPLAYER_MODE="mplayer"
OMXPLAYER_MODE="omxplayer"
MPV_MODE="mpv"

# This is for the new Youtube APIv3 stuff as it stands you would
# need your own key to make this work see:
# https://developers.google.com/youtube/v3/
DEVELOPER_KEY = ""
# This is Russell Brand's The Trews show channel id
# Use search to find other channelids, press 'i' then the video number to see the channel id
CHANNELID = "UCswH8ovgUp5Bdg-0_JTYFNw"

def main():
    """
    Launch yt, allowing user to specify player.
    """

    # Allow the user to specify whether to use mplayer or omxplayer for playing videos.
    parser = argparse.ArgumentParser(prog='yt',formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument("--player",default=MPLAYER_MODE,choices=[MPLAYER_MODE,OMXPLAYER_MODE,MPV_MODE],help="specifies what program to use to play videos")
    parser.add_argument("--novideo", default=False, action='store_true', help="Play selection while suppressing video e.g. Audio only NOTE: This flag is ignored when using omxplayer")
    parser.add_argument("--bandwidth", help="Choose prefered video quality. Example: \"--bandwidth 5\" will try and use codec #5 (240p). Valid choices depend on video ", type=int)
    
    args = parser.parse_args(sys.argv[1:])

    # We are now passing all arguments to the Ui object instead of just the player choice. This allows adding new options.
    ui = Ui(args)
    ui.run()

def main_with_omxplayer():
    """
    Launch yt, using omxplayer.
    """

    parser = argparse.ArgumentParser(prog='pi-yt')

    # Albert - November 23rd
    # Fixing broken pi-yt: Invoking the Ui passing parameters in the same way as it done from main()
    #
    parser.add_argument('--player', default=OMXPLAYER_MODE)
    parser.add_argument('--novideo', default=False)
    parser.add_argument('--bandwidth', type=int)
    parser.add_argument('--audio', default='local')
    args = parser.parse_args()

    ui = Ui(args)
    ui.run()

class ScreenSizeError(Exception):
    def __init__(self, m = 'Terminal too small to continue'):
        self.message = str(m)

    def __str__(self):
        return m

class Ui(object):
    def __init__(self,args):
        
        # A cache of the last feed result
        self._last_feed = None

        # The ordering
        self._ordering = 'date'

        # Specify the current feed
        # now done with the CHANNELID define above 
        self._feed = standard_feed('')
        # The items to display in the pager
        self._items = None

        # A mapping between ordering name and human-name
        self._ordering_names = {
            'relevance': 'relevance',
            'viewCount': 'view count',
            'date': 'publication date',
            'rating': 'rating',
        }
        
        # Which player to use for playing videos.
        self._player = args.player
        
        # Do we want to display video or just audio.
        self._novideo = args.novideo
        
        # Where do we want audio to go through? (RPi)
        # "local" (analog device) or "hdmi".
        self._audio = 'local'

        # Setting a bandwidth preference order
        if args.bandwidth:
            #bandwidth_order = ["247","/","248","/","244","/","243"]
            #arg_position = bandwidth_order.index(str(args.bandwidth))
            #bandwidth_order_string = ''.join(bandwidth_order[arg_position:])
            #self._bandwidth = bandwidth_order_string
            self._bandwidth = str(args.bandwidth)
        else:
            self._bandwidth = None

    def run(self):
        # Get the locale encoding
        locale.setlocale(locale.LC_ALL, '')
        self._code = locale.getpreferredencoding()
        
        # Start the curses main loop
        curses.wrapper(self._curses_main)

    def _curses_main(self, scr):
        curses.noecho()
        self._screen = scr
        self._screen.keypad(1)

        # Check the screen size
        (h, w) = self._screen.getmaxyx()
        if h < 1:
            raise ScreenSizeError()

        # Initialise the display
        curses.curs_set(0)
        curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_BLACK)
        curses.init_pair(3, curses.COLOR_CYAN, curses.COLOR_BLACK)
        curses.init_pair(4, curses.COLOR_MAGENTA, curses.COLOR_BLACK)
        curses.init_pair(5, curses.COLOR_BLACK, curses.COLOR_GREEN)
        curses.init_pair(6, curses.COLOR_YELLOW, curses.COLOR_BLACK)

        # Set attributes
        self._title_attr = curses.color_pair(1)
        self._uploader_attr = curses.color_pair(6)
        self._bar_attr = curses.color_pair(5)

        self._status = ''
        self._help = [
                ('[/]', 'prev/next '),
                ('o', 'ordering'),
                ('s', 'search'),
                ('1-9', 'choose'),
                ('v', 'choose video'),
                ('d', 'download'),
                ('n', 'toggle novideo'),
        ]

        # Create the windows
        self._main_win = curses.newwin(h-1,w,1,0)
        self._status_bar = curses.newwin(1,w,0,0)
        self._status_bar.bkgd(' ', curses.color_pair(5))
        self._help_bar = curses.newwin(1,w,h-1,0)
        self._help_bar.bkgd(' ', self._bar_attr)

        self._update_screen()
        self._run_pager()

    def _reposition_windows(self):
        (h, w) = self._screen.getmaxyx()
        if h < 3:
            raise ScreenSizeError()

        self._main_win.resize(h-1, w)
        self._status_bar.resize(1, w)
        self._help_bar.resize(1, w)
        self._help_bar.mvwin(h-1, 0)

    def _input(self, prompt):
        (h, w) = self._screen.getmaxyx()
        if w < len(prompt) + 2:
            raise ScreenSizeError()

        self._help_bar.erase()
        self._help_bar.addstr(0, 0, ('%s:' % (prompt,)).encode(self._code))
        self._help_bar.refresh()
        input_win = curses.newwin(1, w-len(prompt)-2, h-1, len(prompt)+2)
        input_win.bkgd(' ', self._bar_attr)
        curses.curs_set(1)
        curses.echo()
        try:
            s = input_win.getstr(0,0)
        except KeyboardInterrupt:
            s = None
        curses.noecho()
        curses.curs_set(0)
        return s

    def _get_feed(self, count, pagetoken):
        count = min(count, 25) # 25 is the max number of results we can get in one go
        self._show_message(u'Talking to YouTube\u2026')
        self._last_feed = self._feed['fetch_cb'](count, self._ordering, pagetoken)
        return self._last_feed

    def _update_screen(self):
        self._reposition_windows()
        (h, w) = self._main_win.getmaxyx()

        # Show the items in the window
        self._main_win.erase()
        if self._items is not None and len(self._items) > 0:
            self._show_video_items(self._items)
        self._main_win.refresh()

        # Update the help bar
        self._help_bar.erase()
        if w > 2:
            self._add_table_row(self._help, 0, 0, w-1, self._bar_attr, max_width=16, win=self._help_bar)
        self._help_bar.refresh()

        # Update the status bar
        self._status_bar.erase()
        if w > 2:
            self._status_bar.addstr(0, 0, truncate(self._status, w-1).encode(self._code))
        self._status_bar.refresh()

    def _run_pager(self):
        idx = 0
        pagetoken = ''
        while True:
            # Get size of window and => number of items/page
            (h, w) = self._main_win.getmaxyx()
            n_per_page = h // 3

            # Get the items for the current page
            feed = self._get_feed(n_per_page, pagetoken)
            self._items = None
            if feed is not None:
                feed = self._get_feed(n_per_page, pagetoken)
                self._items = feed['items']
                if len(self._items) > n_per_page:
                    self._items = self._items[:n_per_page]

            if self._items is not None:
                self._status = 'Showing %i-%i of %i in %s' % (idx+1, idx+len(self._items), feed['pageInfo']['totalResults'], self._feed['description'])
            else:
                self._status = 'No results for %s' % (self._feed['description'],)

            if self._ordering in self._ordering_names:
                self._status += ' ordered by ' + self._ordering_names[self._ordering]

            if self._novideo:
                self._status += ' [no video]'

            # Update the screen with the new items
            self._update_screen()

            c = self._main_win.getch()
            if c == ord('q'): # quit
                break
            elif c == ord(']'): # next
                idx += n_per_page
                pagetoken = self._last_feed['nextPageToken']
            elif c == ord('['): # previous
                if idx > n_per_page:
                    idx -= n_per_page
                else:
                    idx = 0
                pagetoken = self._last_feed['prevPageToken'] if 'prevPageToken' in self._last_feed else ''
            elif c == ord('s'): # search
                s = self._input('search')
                if s is not None and len(s) > 0:
                    self._feed = search(s)
                    self._last_feed = None
                    self._ordering = 'relevance'
                    idx = 0
            elif c == ord('v'): # video
                s = self._input('number')
                if s is not None:
                    try:
                        self._play_video(int(s) - 1)
                    except ValueError:
                        pass
            elif c == ord('d'): # download
                s = self._input('download number')
                if s is not None:
                    try:
                        self._download_video(int(s) - 1)
                    except ValueError:
                        pass
            elif c >= ord('1') and c <= ord('9'): # specific video
                self._play_video(c - ord('1'))
            elif c == ord('o'): # ordering
                self._show_message('Order by: (v)iew count, (r)elevance, (p)ublication date or ra(t)ing?')
                oc = self._main_win.getch()
                self._ordering = None
                
                while self._ordering is None:
                    if oc == ord('r'):
                        self._ordering = 'relevance'
                    elif oc == ord('v'):
                        self._ordering = 'viewCount'
                    elif oc == ord('p'):
                        self._ordering = 'date'
                    elif oc == ord('t'):
                        self._ordering = 'rating'

                self._last_feed = None
                idx = 0
            elif c == ord('i'): # ordering
                self._show_message('Get ch id for video 1-9?')
                oc = self._main_win.getch()
                info_num = None
                while info_num is None:
                   if oc >= ord('1') and oc <= ord('9'):
                       info_num = int(chr(oc))
                       self._show_message(feed['items'][info_num]['snippet']['channelId'])
                       #self._show_message(str(info_num))
                       time.sleep(10)
            elif c == ord('n'): # toggle novideo
                self._novideo = not self._novideo


    def _play_video(self, idx):
        # idx is 0-based(!)
        if self._items is None or idx < 0 or idx >= len(self._items):
            return
        item = self._items[idx]
        url = "http://www.youtube.com/watch?v=" + item['id']['videoId']
        self._show_message('Playing ' + url)
        play_url(url,self._player,self._novideo,self._bandwidth,self._audio)

    def _download_video(self, idx):
        # idx is 0-based(!)
        if self._items is None or idx < 0 or idx >= len(self._items):
            return
        item = self._items[idx]
        url = item['player']['default']
        fo = download_url(url, self._novideo, self._bandwidth)
        self._stream_message(fo, 'Downloading ' + item['title'])

    def _show_video_items(self, items):
        # Get size of window and maximum number of items per page
        (h, w) = self._main_win.getmaxyx()
        n_per_page = h // 3

        # How many items should we show?
        n_to_show = min(n_per_page, len(items))

        # Print the results along with an index number
        maxw = len(str(len(items)))

        n = 1; y = 0
        for item in items[:n_to_show]:
            num_str = ('%'+str(maxw)+'i') % (n,)
            if w > maxw:
                self._main_win.addstr(y, 0, num_str.encode(self._code), curses.color_pair(4) | curses.A_BOLD)
            self._add_video_item(y, maxw + 1, w-maxw-1, item)
            n += 1
            y += 3

    def _add_video_item(self, y, x, w, item):
        # Bail if we have _no_ horizontal space
        if w <= 0:
            return

        title = item['snippet']['title']
        uploader = item['uploader']

        duration = item['duration'] if 'duration' in item else '' 
        duration = duration[+2:]
        comments = int(item['commentCount']) if 'commentCount' in item else 0
        views = int(item['viewCount']) if 'viewCount' in item else 0

        # Show the title and uploader, prioritising the title
        if len(uploader) > w:
            self._main_win.addstr(y,x,truncate(title, w).encode(self._code), self._title_attr)
        else:
            self._main_win.addstr(y,x,truncate(title, w-len(uploader)).encode(self._code), self._title_attr)
            self._main_win.addstr(y,x+w-len(uploader), uploader.encode(self._code), self._uploader_attr)

        desc = item['snippet']['description'] 
        if desc is None or len(desc.strip()) == 0:
            desc = 'No description'
        desc = re.sub(r'[\n\r]', r' ', desc)
        self._main_win.addstr(y+1,x,truncate(desc, w).encode(self._code), curses.color_pair(2))
        self._add_table_row([
                ('d', '%s' % duration),
                ('v', number(views)),
                ('c', number(comments)),
            ], y+2, x, w, curses.color_pair(3) | curses.A_DIM, max_width=40)

    def _show_message(self, s):
        # Check length of message
        (h, w) = self._main_win.getmaxyx()
        if w < 3 or h < 3:
            return

        winw = min(len(s)+2, w)

        mw = self._setup_message_window(3, winw)
        mw.addstr(1,1, truncate(s,winw-2).encode(self._code))
        mw.refresh()

    def _stream_message(self, fo, title=""):
        """Take in a file object and continual read it and display resulting
        output in a window"""

        winh = 9

        (h, w) = self._main_win.getmaxyx()
        if w < 3 or h < winh:
            return

        winw = min(max(len(title) + 4, 80), w)
        mw = self._setup_message_window(winh, winw)

        if title != "":
            title = " " + title + " "
            mw.addstr(0, (winw - len(title))//2, title.encode(self._code))
            mw.refresh()

        status = " Press ctrl-c to cancel "
        mw.addstr(winh-1, (winw - len(status))//2, status.encode(self._code))
        mw.refresh()

        line = 1
        linecontent = ""

        while True:
            try:
                ch = fo.stdout.read(1)
            except KeyboardInterrupt:
                break

            # If we're done, display close message and stop
            if ch == '' and fo.poll() != None:
                close_message = " Press a key to close "
                mw.addstr(winh-1, (winw - len(close_message))//2, close_message.encode(self._code))
                mw.refresh()
                c = self._main_win.getch()
                break

            # If we didn't encounter a new line or carriage return char,
            # accumulate our linecontent buffer
            if ch != "\n" and ch != "\r":
                linecontent += ch
                continue

            # Clean out the current line
            mw.addstr(line, 1, " " * (winw-2))

            # Display our line
            mw.addstr(line, 1, truncate(linecontent, winw-2).encode(self._code))
            mw.refresh()
            linecontent = ""

            # A carriage return should stay on the same line
            if ord(ch) != 13:
                line = line + 1

            # Make sure we don't try to output past the window
            if line > winh-2:
                line = winh-2

    def _setup_message_window(self, height, width):
        (h, w) = self._main_win.getmaxyx()
        mw = curses.newwin(height, width, (h//2)-(height//2)-2, (w-width)//2)
        mw.bkgd(' ', curses.color_pair(5))
        mw.erase()
        mw.border()

        return mw

    def _add_table_row(self, data, y, x, w, attr, max_width=None, min_width=4, win=None):
        if win is None:
            win = self._main_win
        n_keys = len(data)
        cell_w = max(w // n_keys, min_width)
        if max_width is not None:
            cell_w = min(cell_w, max_width)
        for k,v in data:
            if x < w:
                win.addstr(y, x, truncate('%s:%s' % (k,v), min(w-x, cell_w)).encode(self._code), attr)
            x += cell_w

def truncate(s, n):
    if(len(s) <= n):
        return s
    if(n < 1):
        return ''
    return s[:(n-1)] + u'\u2026'

def duration(n):
    if n < 60*60:
        return '%im%02is' % (n//60, n%60)
    return '%sh%-2im%02is' % (n//(60*60), (n%(60*60))//60, n%60)

def number(n):
    if n < 1000:
        return str(n)
    if n < 1000000:
        return '%.1fk' % (n/1000.0,)
    return '%.1fM' % (n//1000000.0,)

def download_url(url,novideo,bandwidth):
    yt_dl = subprocess.Popen(['youtube-dl', url], stdout = subprocess.PIPE, stderr = subprocess.PIPE)
    return yt_dl

def play_url(url,player,novideo,bandwidth,audio):
    t_url=url
    assert player in [MPLAYER_MODE,OMXPLAYER_MODE,MPV_MODE]
    if player == MPV_MODE:
        # mpv can handle youtube URLs through quvi
        play_url_mpv(url, novideo)
    elif player == MPLAYER_MODE:
        url = get_playable_url(url, novideo, bandwidth)
        play_url_mplayer(url,novideo,t_url,bandwidth)
    else:
        url = get_playable_url(url, novideo, bandwidth)
        play_url_omxplayer(url,audio)

def get_playable_url(url, novideo, bandwidth):
    t_url=url
    if novideo:
      #Choosing a low bitrate codec since we will be dropping the video anyway
      call = "youtube-dl -g -f " + "171/140/136/247/18/43/133 " + url
      url = os.popen(call).read()
    elif bandwidth:
      #'subprocess.Popen' is not calling youtube-dl properly when using '-f' flag, so here we are using 'os.popen'
      call = "youtube-dl -g -f " + bandwidth + " " + url
      url = os.popen(call).read()
      
      
    else:
      call = "youtube-dl -g -f 22 " + url
      url = os.popen(call).read()
    return url
    
def play_url_mplayer(url,novideo,t_url,bandwidth):
    
    if novideo or not bandwidth:
	player = subprocess.Popen(
	['vlc', '--quiet','--no-video-title-show','--play-and-exit', url.decode('UTF-8').strip()],
	stdout = subprocess.PIPE, stderr = subprocess.PIPE)
    else:
	call = "youtube-dl -g -f " + "171 " + t_url
	t_url = os.popen(call).read()
	player = subprocess.Popen(
	['vlc', '--quiet','--no-video-title-show','--play-and-exit', url.decode('UTF-8').strip(),'--input-slave', t_url.decode('UTF-8').strip()],
	stdout = subprocess.PIPE, stderr = subprocess.PIPE)
	    
def play_url_omxplayer(url,audio):
    player = subprocess.Popen(
            ['omxplayer', '-o%s' % audio, url.decode('UTF-8').strip()],
            stdout = subprocess.PIPE, stderr = subprocess.PIPE)
    player.wait()

    # fix black X screen after omxplayer playback
    # http://elinux.org/Omxplayer#Black_screen_after_playback
    # This causes an error when playing from Raspberry Pi command line so commenting out for now
    # os.system('xrefresh -display :0')

def play_url_mpv(url, novideo):
    player = subprocess.Popen(['mpv', '--really-quiet', '--', url],
            stdout = subprocess.PIPE, stderr = subprocess.PIPE)
    player.wait()

def get_video_info(search_results):

        count = 0
        video_ids = ''
        for search_item in search_results["items"]:
          video_ids += search_item["id"]["videoId"] + ','
          search_results["items"][count]["uploader"] = " "
          count += 1

        url = 'https://www.googleapis.com/youtube/v3/videos'
        query = {
            'part': 'statistics, contentDetails',
            'id': video_ids,
            'key': DEVELOPER_KEY,
        }
        video_results  = json.load(urllib2.urlopen('%s?%s' % (url, urllib.urlencode(query))))
        count = 0
        for video_item in video_results["items"]:
          search_results["items"][count]["duration"] = video_item["contentDetails"]["duration"]
          search_results["items"][count]["viewCount"] = video_item["statistics"]["viewCount"]
          search_results["items"][count]["commentCount"] = 0 #video_item["statistics"]["commentCount"]
          count += 1
        return search_results

def search(terms):
    def fetch_cb(maxresults, ordering, pagetoken):
        url = 'https://www.googleapis.com/youtube/v3/search'
        query = {
            'part': 'id,snippet',
            'maxResults': maxresults,
            'order': ordering,
            'pageToken': pagetoken,
            'q' : terms,
            'type': 'video',
            'key': DEVELOPER_KEY,
        }
        search_results = json.load(urllib2.urlopen('%s?%s' % (url, urllib.urlencode(query))))

        return get_video_info(search_results)

    return { 'fetch_cb': fetch_cb, 'description': 'search for "%s"' % (terms,) }

def standard_feed(feed_name):
    
    def fetch_cb( maxresults,ordering,pagetoken):

        url = 'https://www.googleapis.com/youtube/v3/search'
        query = {
            'part': 'id,snippet',
            'channelId': CHANNELID,
            'maxResults': maxresults,
            'order': ordering,
            'pageToken': pagetoken,
            'type': 'video',
            'key': DEVELOPER_KEY,
        }
        search_results = json.load(urllib2.urlopen('%s?%s' % (url, urllib.urlencode(query))))

        return get_video_info(search_results)

    feed = { 'fetch_cb': fetch_cb, 'description': 'standard feed' }
    return feed
                 


# Make it easy to run module by itself without using external tools to deploy it and
# create additional launch scripts.
if __name__ == "__main__":
    main()
