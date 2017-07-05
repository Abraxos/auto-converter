'''Contains all the properties and methods necessary to manage mediainfo objects'''
from subprocess import check_output
from re import compile as cmpl

from constants import HEIGHT, WIDTH, BITRATES, AUDIO_KEYS, BITRATE_KEYS
from utils import str2float

class MediaInfo(object):
    '''An object that represents metadata about a media file based on the mediainfo linux program'''
    def __init__(self, file_path):
        '''Constructor for a media info object that represents the metadata of a media file'''
        self.file_path = file_path
        self.info = {}
        char = None
        output = check_output('mediainfo "' + self.file_path + '"', shell=True).decode('UTF-8')
        for line in output.split('\n'):
            match = cmpl(r'(.+[^\s])\s+: (.+)').match(line)
            if match:
                self.info[char][match.group(1)] = match.group(2)
            elif len(line) > 1:
                char = line
                self.info[char] = {}

    def video_height(self):
        '''Returns the height of the video in pixels'''
        return int(str2float(self.info["Video"]["Height"]) if \
                   str2float(self.info["Video"]["Height"]) < HEIGHT else HEIGHT)

    def video_width(self):
        '''Returns the width of the video in pixels'''
        return int(str2float(self.info["Video"]["Width"]) if \
                   str2float(self.info["Video"]["Width"]) < WIDTH else WIDTH)

    def _bitrate(self):
        A = self.info[next(a for a in AUDIO_KEYS if a in self.info)] if \
            [a for a in AUDIO_KEYS if a in self.info] else None
        if A:
            return A[next(b for b in BITRATE_KEYS if b in A)] if \
                   [b for b in BITRATE_KEYS if b in A] else None
        else:
            return None
        
    def abr(self):
        '''Returns the audiobitrate in human-reabable kilobytes'''
        def pick_bitrate(bitrate):
            '''Picks the best possible bitrate out of the BITRATES array'''
            br = int(str2float(next(b for b in bitrate.split('/') \
                     if 'Unknown' not in b)))
            if br in BITRATES:
                return br
            elif br < min(BITRATES):
                return min(BITRATES)
            elif br > max(BITRATES):
                return max(BITRATES)
            else:
                return min(BITRATES, key=lambda x: abs(x-br))
        B = self._bitrate()
        if B:
            return str(pick_bitrate(B)) + 'k'
        else:
            return None

    def more_than_sd(self):
        try:
            if str2float(self.info["Video"]["Width"]) > WIDTH:
                return True
            elif str2float(self.info["Video"]["Height"]) > HEIGHT:
                return True
            elif str2float(self._bitrate()) > max(BITRATES):
                return True
            return False
        except KeyError:
            print("Media info for {} is invalid, cannot compare to SD".format(self.file_path))
            return False
