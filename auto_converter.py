#!/usr/bin/python3
'''A utility for listening on an input directory and converting any media files placed in it.'''

from os.path import join, basename, splitext, isfile, abspath
from os import stat
from subprocess import check_output, run, PIPE
from re import compile as cmpl
import sys
from shutil import move as mv
from traceback import print_exception
from configparser import ConfigParser
from argparse import ArgumentParser
from multiprocessing import Process, Manager
from time import sleep
import psutil

from twisted.internet.inotify import INotify, humanReadableMask
from twisted.python.filepath import FilePath
from twisted.internet import reactor

ACCEPTED_EVENTS = ['attrib', 'moved_to']
VIDEO_FILE_EXTENSIONS = ['.mp4', '.mkv', '.avi', '.wmv', '.flv', '.mpg',
                         '.mpeg', '.ts', '.m4v']
HEIGHT = 640
WIDTH = 1136
BITRATES = [56, 64, 80, 96, 112, 128, 160, 192]
BITRATE_KEYS = ["Bit rate", "Maximum bit rate"]
AUDIO_KEYS = ["Audio", "Audio #1"]
CONVERSION_RESULT = 'conversion result'
CONVERSION_FAILURE_TOO_SMALL = 'resulting file is too small'
CONVERSION_SUCCESS = 'conversion success'
CONVERSION_FAILURE_ERROR = 'fuck'
INPUT = 'input_directory'
OUTPUT = 'output_directory'
COMPLETED = 'completed_directory'
ERROR = 'error_directory'

def str2float(string):
    '''Converts a string to a floating point value'''
    return float(cmpl(r'[^\d.]+').sub('', string))

def human_readable_size(size_b):
    '''Given a size, in bytes, this function outputs a human-readable size in
       the most convenient units.'''
    size_float = float(size_b)
    size_unit = 'BYTES'
    if size_float > 1024:
        size_float = size_float / 1024
        size_unit = 'KiB'
        if size_float > 1024:
            size_float = size_float / 1024
            size_unit = 'MiB'
            if size_float > 1024:
                size_float = size_float / 1024
                size_unit = 'GiB'
                if size_float > 1024:
                    size_float = size_float / 1024
                    size_unit = 'TiB'
    return '%.2f %s' % (size_float, size_unit)

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
            else: return min(BITRATES, key=lambda x: abs(x-br))
        A = self.info[next(a for a in AUDIO_KEYS if a in self.info)] if \
            [a for a in AUDIO_KEYS if a in self.info] else None
        if A:
            B = A[next(b for b in BITRATE_KEYS if b in A)] if \
                [b for b in BITRATE_KEYS if b in A] else None
            if B:
                return str(pick_bitrate(B)) + 'k'
            else: return None
        else:
            return None

def child_ffmpeg_process(prc):
    '''Returns a psutil.Process object referencing the ffmpeg subprocess'''
    children = psutil.Process(prc.pid).children()
    for child in children:
        if child.name() == 'ffmpeg':
            return child

def file_size(filepath):
    '''Returns the size of a file in bytes'''
    return stat(filepath).st_size

def get_positions(process):
    '''Returns the positions for all open files'''
    return {open_file.path:open_file.position for open_file in process.open_files()}

class Converter(object):
    '''An object responsible for managing media conversion processes'''
    def __init__(self, config):
        self.config = config
        self.dst_dir = self.config[OUTPUT]
        self.p_string = ''

    def _convert(self, src, result_dict):
        '''Executes the conversion subprocess'''
        run(self.conversion_command(src), stdout=PIPE, stderr=PIPE)
        if stat(self.dst(src)).st_size < 10000:
            result_dict[CONVERSION_RESULT] = CONVERSION_FAILURE_TOO_SMALL
        else:
            result_dict[CONVERSION_RESULT] = CONVERSION_SUCCESS

    def _update_status(self, dst_size, src_pos, src_size):
        '''Updates the status on the screen'''
        print('\b' * (len(self.p_string) + 2), end='')
        print(' ' * (len(self.p_string)), end='')
        print('\b' * (len(self.p_string) + 2), end='')
        self.p_string = ("PROGRESS: OUTPUT_SIZE: %s PROCESSED: %s / %s COMPLETE"
                         ": %.2f%% RATE: ??ps ETA: ??s") % (
                             human_readable_size(dst_size),
                             human_readable_size(src_pos),
                             human_readable_size(src_size),
                             float(src_pos)/float(src_size) * 100.0)
        print(self.p_string, end='')
        sys.stdout.flush()

    def dst(self, filepath):
        '''Generates the destination file path from a given source filepath'''
        return join(self.dst_dir, splitext(basename(filepath))[0] + '.mp4')

    def conversion_command(self, filepath):
        '''Generates a conversion command'''
        info = MediaInfo(filepath)
        audio_bitrate = info.abr()
        height = info.video_height()
        width = info.video_width()
        print("Converting {} to: {}x{} Bit-Rate: {}"\
              .format(filepath, width, height, audio_bitrate))
        cmd = ['ffmpeg', '-stats', '-y', '-i', filepath, '-s:v',
               str(width) + 'x' + str(height)]
        cmd.extend(['-acodec', 'mp3', '-ab', audio_bitrate] \
                    if audio_bitrate else ['-acodec', 'copy'])
        cmd.extend(['-c:v', 'libx264', self.dst(filepath)])
        return cmd

    def convert(self, filepath):
        '''Converts a file'''
        manager = Manager()
        res = manager.dict()
        filepath = abspath(filepath)
        prc = Process(target=self._convert, args=(filepath, res))
        prc.start()
        while prc.is_alive():
            ffmpeg_prc = child_ffmpeg_process(prc)
            if ffmpeg_prc:
                positions = get_positions(ffmpeg_prc)
                self._update_status(file_size(self.dst(filepath)),
                                    positions[filepath],
                                    file_size(filepath))
            sleep(2)
        print(res)

class DirectoryHandler(object):
    '''An object for watching a directory and converting any files that appear in it.'''
    def __init__(self, dir_path, config):
        '''Construct a directory handler'''
        self.dir_path = dir_path
        self.config = config
        self.converter = Converter(self.config)

    def handle_new_file(self, filepath):
        '''Handles a new file in the directory'''
        filename = basename(filepath.decode('UTF-8'))
        err = join(self.config[ERROR], filename)
        done = join(self.config[COMPLETED], filename)
        print("[{}]: New File: {}".format(self.config, filepath))
        try:
            self.converter.convert(filepath)
            mv(filepath, done)
        except Exception as e: # pylint: disable=W0703
            print("[{}][{}]: ERROR - {}".format(self.config, filename, e))
            exc_info = sys.exc_info()
            print_exception(*exc_info)
            try:
                mv(filepath, err)
            except Exception as e: # pylint: disable=W0703
                print("[{}][{}]: ERROR - Unable to move to error directory... "\
                      .format(self.config, filename))

    def on_directory_changed(self, _, filepath, mask):
        '''Handles directory changes'''
        filepath = filepath.path.decode('UTF-8')
        # config_section = DIRECTORY_TO_SECTION_MAP[dirname(filepath)]
        mask = humanReadableMask(mask)
        print("Event {} on {}".format(mask, filepath))
        if isfile(filepath):
            if splitext(filepath)[1] in VIDEO_FILE_EXTENSIONS:
                if any([a for a in mask if a in ACCEPTED_EVENTS]):
                    self.handle_new_file(filepath)
            else:
                print('Ignoring non-media file: {}'.format(filepath))
        else:
            print('Ignoring directory: {}'.format(filepath))

def main():
    '''Parses arguments, configuration, and launches the reactor'''
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

    config = ConfigParser()
    config.read(args.configuration_file)

    notifier = INotify()
    for section in config.sections():
        input_dir = config[section][INPUT]
        dir_handler = DirectoryHandler(input_dir, config[section])
        notifier.watch(FilePath(dir_handler.dir_path),
                       callbacks=[dir_handler.on_directory_changed])
        print("[{}] Watching: {}".format(section, config[section]['input_directory']))
    notifier.startReading()
    reactor.run() # pylint: disable=E1101

if __name__ == '__main__':
    main()
