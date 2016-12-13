#!/usr/bin/python3

from os.path import dirname, join, basename, splitext
from os import stat
from subprocess import check_output
from subprocess import call
from re import compile as cmpl
import sys
from shutil import move as mv
from traceback import print_exception
from configparser import ConfigParser
from argparse import ArgumentParser

from twisted.internet.inotify import INotify, humanReadableMask
from twisted.python.filepath import FilePath
from twisted.internet import reactor

ACCEPTED_EVENTS = ['attrib', 'moved_to']
VIDEO_FILE_EXTENSIONS = [b'.mp4', b'.mkv', b'.avi', b'.wmv', b'.flv', b'.mpg', b'.mpeg', b'.ts']
HEIGHT = 640
WIDTH = 1136
BITRATES = [56, 64, 80, 96, 112, 128, 160, 192]
BITRATE_KEYS = ["Bit rate", "Maximum bit rate"]
AUDIO_KEYS = ["Audio", "Audio #1"]

def generate_directory_section_mapping(configuration):
    return {bytes(configuration[section]['input_directory'], encoding='UTF-8') : section for section in configuration.sections()}

def str2float(s):
    return float(cmpl(r'[^\d.]+').sub('', s))

def abr(M):
    def pick_bitrate(B):
        br = int(str2float(next(b for b in B.split('/') if 'Unknown' not in b)))
        if br in BITRATES: return br
        elif br < min(BITRATES): return min(BITRATES)
        elif br > max(BITRATES): return max(BITRATES)
        else: return min(BITRATES, key=lambda x:abs(x-br))
    A = M[next(a for a in AUDIO_KEYS if a in M)] if [a for a in AUDIO_KEYS if a in M] else None
    if A:
        B = A[next(b for b in BITRATE_KEYS if b in A)] if [b for b in BITRATE_KEYS if b in A] else None
        if B:
            return str(pick_bitrate(B)) + 'k'
        else: return None
    else:
        return None

def video_height(M):
    return int(str2float(M["Video"]["Height"]) if str2float(M["Video"]["Height"]) < HEIGHT else HEIGHT)

def video_width(M):
    return int(str2float(M["Video"]["Width"]) if str2float(M["Video"]["Width"]) < WIDTH else WIDTH)

def mediainfo(f):
    M = {}
    c = None
    output = check_output(b'mediainfo "' + f + b'"', shell=True).decode('UTF-8')
    for line in output.split('\n'):
        m = cmpl(r'(.+[^\s])\s+: (.+)').match(line)
        if m: M[c][m.group(1)] = m.group(2)
        elif len(line) > 1:
            c = line
            M[c] = {}
    return M

def handle_new_file(config_section, filepath, dst_dir, done_dir, err_dir):
    try:
        print("[{}]: New File: {}".format(config_section, filepath))
        filename = basename(filepath.decode('UTF-8'))
        M = mediainfo(filepath)
        ab = abr(M)
        h = video_height(M)
        w = video_width(M)
        print("[{}][{}]: Converting to: {}x{} Bit-Rate: {}"
               .format(config_section, filename, w, h, ab))
        dst = join(dst_dir, splitext(filename)[0] + '.mp4')
        err = join(err_dir, filename)
        done = join(done_dir, filename)
        cmd = ['ffmpeg', '-stats', '-y', '-i', filepath.decode('UTF-8'), '-s:v', str(w) + 'x' + str(h)]
        cmd.extend(['-acodec', 'mp3', '-ab', ab] if ab else ['-acodec','copy'])
        cmd.extend(['-c:v', 'libx264', dst])
        print("[{}][{}]: Executing: {}".format(config_section, filename, cmd))
        call(cmd)
        if stat(dst).st_size < 10000:
            raise Exception("Conversion failed! Output too small!")
        else:
            mv(filepath, done)
    except Exception as e: # pylint: disable=W0703
        print("[{}][{}]: ERROR - " + str(e))
        exc_info = sys.exc_info()
        print_exception(*exc_info)
        try:
            mv(filepath, err)
            # pass
        except Exception as e: # pylint: disable=W0703
            print("[{}][{}]: ERROR - Unable to move to error directory... " + str(e))

def on_directory_changed(_, filepath, mask):
    config_section = DIRECTORY_TO_SECTION_MAP[dirname(filepath.path)]
    mask = humanReadableMask(mask)
    print("Event {} on {}".format(mask, filepath))
    if (splitext(filepath.path)[1] in VIDEO_FILE_EXTENSIONS):
        if any([a for a in mask if a in ACCEPTED_EVENTS]):
            handle_new_file(config_section, filepath.path,
                            CONFIG[config_section]['output_directory'],
                            CONFIG[config_section]['completed_directory'],
                            CONFIG[config_section]['error_directory'])
    else:
        print('Ignoring non-media file: {}'.format(filepath.path))

if __name__ == '__main__':
    global DIRECTORY_TO_SECTION_MAP
    global CONFIG

    arg_parser = ArgumentParser(description='A utility that can be configured \
                                             to watch a set of directories for \
                                             new media files and when a new \
                                             media file appears, it will be \
                                             automatically converted to a \
                                             preset SD format.')
    arg_parser.add_argument('configuration_file', help='An INI format \
                            configuration file detailing the directories to be \
                            watched.')
    args = arg_parser.parse_args()

    CONFIG = ConfigParser()
    CONFIG.read(args.configuration_file)
    DIRECTORY_TO_SECTION_MAP = generate_directory_section_mapping(CONFIG)

    notifier = INotify()
    for section in CONFIG.sections():
        notifier.watch(FilePath(CONFIG[section]['input_directory']),
                       callbacks=[on_directory_changed])
        print("[{}] Watching: {}".format(section, CONFIG[section]['input_directory']))
    notifier.startReading()
    reactor.run() # pylint: disable=E1101
