'''Includes various utility functions for the converter service'''
from re import compile as cmpl
from argparse import ArgumentParser, Action, ArgumentTypeError
import os
from constants import VIDEO_FILE_EXTENSIONS

def str2float(string):
    '''Converts a string to a floating point value'''
    return float(cmpl(r'[^\d.]+').sub('', string))

def percentage(value):
    return "{:0.2f}%".format(value * 100.0)

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

def is_media_file(file_path):
    return (os.path.splitext(file_path)[1] in VIDEO_FILE_EXTENSIONS)

class ReadWriteFile(Action):
    '''Ensures that a given file is both readable and writeable'''
    def __call__(self, parser, namespace, prospective_file, option_str=None):
        if os.access(prospective_file, os.R_OK) and os.access(prospective_file, os.W_OK):
            setattr(namespace, self.dest, prospective_file)
        else:
            raise ArgumentTypeError('{} is either not rewad/writeable or \
                                     does not exist'.format(prospective_file))

def process_converter_args():
    '''Processes command-line arguments for the converter script'''
    parser = ArgumentParser(description='A script to convert a given video file into my SD format')
    parser.add_argument('to_convert', type=str,
                        action=ReadWriteFile,
                        help='A file to be converted, will be replaced by resulting file.')
    args = parser.parse_args()
    return args

def process_converter_service_args():
    '''Processes command-line arguments for the converter service'''
    parser = ArgumentParser(description='A service that watches a directory for \
                                         files that can and should be converted \
                                         and then converts them to SD.')
    parser.add_argument('to_scan', type=str,
                        help='A directory to be checked for files that can be converted')
    args = parser.parse_args()
    return args
