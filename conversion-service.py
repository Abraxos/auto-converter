'''A conversion service that runs every X seconds to convert any
   non-converted files in a given directory'''
from os.path import splitext, join
from os import walk
from time import sleep
from converter import Converter
from mediainfo import MediaInfo
from utils import is_media_file, process_converter_service_args

def should_convert(to_convert_path):
    # TODO: Check if the video file is open in another application
    if is_media_file(to_convert_path):
        # if not an MP4 file, always convert
        if splitext(to_convert_path)[1] != '.mp4':
            return True
        # otherwise, compare the metadata, convert if above SD
        mediainfo = MediaInfo(to_convert_path)
        return mediainfo.more_than_sd()
    else:
        return False

def scan_directory(dir_path):
    '''Returns a list of files that should be converted'''
    to_convert = []
    for root, _, files in walk(dir_path):
        print("Scanning {}".format(root))
        for file_name in files:
            file_path = join(root, file_name)
            if should_convert(file_path):
                to_convert.append(file_path)
    return to_convert

def main():
    args = process_converter_service_args()
    converter = Converter()
    while True:
        to_convert = scan_directory(args.to_scan)
        converter.run_conversion(to_convert[0])
        sleep(60)

if __name__ == '__main__':
    main()
