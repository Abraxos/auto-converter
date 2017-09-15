'''A conversion service that runs every X seconds to convert any
   non-converted files in a given directory'''
from os.path import splitext, join, isfile
from os import walk
from time import sleep
from converter import Converter
from constants import RETRY_LIMIT
from mediainfo import MediaInfo
from utils import is_media_file, process_converter_service_args

def num_errors(error_file_path):
    '''Returns the number of errors for a particular file based
       on their error file'''
    if isfile(error_file_path):
        with open(error_file_path, 'r') as error_file:
            contents = error_file.read()
            try:
                counter = int(contents) + 1
            except: # pylint: disable=bare-except
                counter = 1
            return counter
    else:
        return 0

def should_convert(to_convert_path):
    '''Given a path this function indicates whether the file should be
       converted. Includes a check of whether its a video file, a check
       to make sure that its not currently being converted, and a check
       of the metadata to make sure it hasn't already been converted to
       an SD format'''
    def is_not_buggy(file_path):
        '''Checks that the number of errors for the file is under the limit'''
        name, _ = splitext(file_path)
        error_file = name + '.conversion.error'
        if num_errors(error_file) > RETRY_LIMIT:
            print("Too many errors with {}".format(file_path))
            return False
        return True

    if is_media_file(to_convert_path):
        # if file ends with '.converting.mp4' don't convert
        if to_convert_path.endswith('.converting.mp4'):
            return False
        # if not an MP4 file, always convert
        if splitext(to_convert_path)[1] != '.mp4':
            return is_not_buggy(to_convert_path)
        # otherwise, compare the metadata, convert if above SD
        return is_not_buggy(to_convert_path) and MediaInfo(to_convert_path).more_than_sd()
    else:
        return False

def scan_directory(dir_path):
    '''Returns a list of files that should be converted'''
    to_convert = []
    do_not_convert = []
    for root, _, files in walk(dir_path):
        print("Scanning {}".format(root))
        for file_name in files:
            file_path = join(root, file_name)
            if should_convert(file_path):
                to_convert.append(file_path)
            else:
                do_not_convert.append(file_path)
    print("{} files converted (or don't need to be), {} files left."\
           .format(len(do_not_convert), len(to_convert)))
    return to_convert

def main():
    '''Processes commandline arguments and starts the converter service'''
    args = process_converter_service_args()
    converter = Converter()
    while True:
        to_convert = scan_directory(args.to_scan)
        if to_convert:
            converter.run_conversion(to_convert[0])
        sleep(30)

if __name__ == '__main__':
    main()
