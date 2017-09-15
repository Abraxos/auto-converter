'''A script and set of functions for converting video files to a standard format'''
from os.path import splitext, getsize, isfile
from os import rename, remove
import sys
from time import sleep
from multiprocessing import Process, Manager
from subprocess import check_call, SubprocessError
from aenum import IntEnum
from arrow import utcnow as now
import psutil
from mediainfo import MediaInfo, MediaInfoError
from utils import process_converter_args, human_readable_size, percentage
from utils import log_successful_conversion, log_failed_conversion

ConversionStatus = IntEnum('ConversionStatus', 'NONE RUNNING PAUSED STOPPED ERROR DONE')

class Conversion(object):
    def __init__(self, src_file_path, dst_file_path, log_file_path):
        self.src = src_file_path
        self.dst = dst_file_path
        self.log = log_file_path
        try:
            self.info = MediaInfo(self.src)
            self.audio_bitrate = self.info.abr()
            self.height = self.info.video_height()
            self.width = self.info.video_width()
        except MediaInfoError:
            self.agent_result = {'error', 'Unable to load media info for: {}'.format(self.src)}
            raise MediaInfoError
        self.agent = None
        self.agent_result = None
        self.agent_info = None
        self.ffmpeg_proc = None
        self.ffmpeg_proc_info = None
        self.start_time = None
    def _execute(self, return_dict):
        with open(self.log, 'w+') as log_file:
            try:
                check_call(self._cmd(), stderr=log_file, stdout=log_file)
            except SubprocessError as conversion_error:
                return_dict['error'] = conversion_error
    def start(self):
        '''Starts the conversion subprocess'''
        self.start_time = now()
        print("Converting {} to: {}x{} Bit-Rate: {}"\
              .format(self.src, self.width, self.height, self.audio_bitrate))
        manager = Manager()
        self.agent_result = manager.dict()
        self.agent = Process(target=self._execute, args=(self.agent_result,))
        self.agent.start()
        self.agent_info = psutil.Process(self.agent.pid)
        sleep(2.0)
        self.ffmpeg_proc = next(c for c in self.agent_info.children() if c.name() == 'ffmpeg')
        self.ffmpeg_proc_info = psutil.Process(self.ffmpeg_proc.pid)
    def pause(self):
        '''Attempts to pause the conversion subprocess if its ongoing'''
        # TODO: Implement conversion pause
        pass
    def resume(self):
        '''Attempts to resume the conversion subprocess if its paused'''
        # TODO: Implement conversion resume
        pass
    def elapsed(self):
        '''Outputs a timedelta indicating the time that's elapsed since conversion started'''
        return now() - self.start_time
    def eta(self):
        '''Outputs a timedelta indicating the estimated time to completion'''
        try:
            return (self.elapsed() / self.progress()) - self.elapsed()
        except ZeroDivisionError:
            return float('inf')
    def progress(self):
        '''Returns a float representing the conversion progress as a percentage'''
        try:
            return self.position() / self.input_size()
        except ZeroDivisionError:
            return 0
    def position(self):
        '''Returns the position in the input file which is a measure of progress'''
        try:
            input_file = self.ffmpeg_proc_info.open_files()[-2]
        except psutil.AccessDenied:
            return 0
        return input_file.position
    def input_size(self):
        '''Returns the size of the input file'''
        return getsize(self.src)
    def output_size(self):
        '''Returns the size of the output file'''
        try:
            output_file = self.ffmpeg_proc_info.open_files()[-1]
        except psutil.AccessDenied:
            return 0
        return output_file.position
    def state(self):
        '''Returns the status of the FFMPEG conversion process'''
        return self.ffmpeg_proc_info.status()
    def result(self):
        '''Returns the result_dict of the conversion agent process'''
        return self.agent_result
    def _cmd(self):
        '''Generates a conversion command'''
        cmd = ['ffmpeg', '-stats', '-y', '-i', self.src, '-s:v',
               str(self.width) + 'x' + str(self.height)]
        cmd.extend(['-acodec', 'mp3', '-ab', self.audio_bitrate] \
                    if self.audio_bitrate else ['-acodec', 'copy'])
        cmd.extend(['-c:v', 'libx264', self.dst])
        return cmd

def increment_error_counter(error_file_path):
    '''Given a file whose only contents are a counter of errors
       this function will increment it'''
    if isfile(error_file_path):
        with open(error_file_path, 'r') as error_file:
              contents = error_file.read()
    else:
        contents = '0'
    with open(error_file_path, 'w+') as error_file:
        print("{}: {} Errors".format(error_file_path, contents))
        try:
            counter = int(contents) + 1
        except:
            counter = 1
        error_file.write(str(counter))

class Converter(object):
    '''Manages conversion objects and provides and interface to
       start/stop/pause/resume/recover conversions'''
    def __init__(self):
        self.conversion = None
    def run_conversion(self, src_file_path):
        '''Starts a conversion subprocess for a given source'''
        dst_file_path = splitext(src_file_path)[0] + '.converting.mp4'
        final_dst_file_path = splitext(src_file_path)[0] + '.mp4'
        log_file_path = splitext(src_file_path)[0] + '.conversion.log'
        error_file_path = splitext(src_file_path)[0] + '.conversion.error'
        try:
            self.conversion = Conversion(src_file_path, dst_file_path, log_file_path)
            self.conversion.start()
            converting = True
        except (StopIteration, MediaInfoError):
            print("Error, failed to start conversion of {}".format(src_file_path))
            converting = False
        while converting:
            try:
                elapsed = str(self.conversion.elapsed())
                eta = str(self.conversion.eta())
                output_size = human_readable_size(self.conversion.output_size())
                progress = percentage(self.conversion.progress())
                if output_size is not None and progress is not None:
                    output_str = "Converting [{}]: {} Progress {} ETA: {}\r".format(elapsed,
                                                                                    output_size,
                                                                                    progress, eta)
                    sys.stdout.write(output_str)
                sleep(0.5)
                sys.stdout.flush()
            except psutil.NoSuchProcess:
                print()
                print("Conversion process ended...")
                break
        result = {'error':'Conversion could not be started'} if not self.conversion else self.conversion.result()
        if 'error' in result:
            print("There was an error during conversion: {}".format(result))
            increment_error_counter(error_file_path)
            log_failed_conversion(log_file_path)
        elif getsize(dst_file_path) < 10000:
            print("There was an error during conversion: {} is too small...".format(dst_file_path))
            increment_error_counter(error_file_path)
            log_failed_conversion(log_file_path)
        elif not MediaInfo(dst_file_path).valid():
            print("There was an error during conversion: {} media info is invalid".format(dst_file_path))
            increment_error_counter(error_file_path)
            log_failed_conversion(log_file_path)
        else:
            remove(src_file_path)
            rename(dst_file_path, final_dst_file_path)
            log_successful_conversion(log_file_path)

    def status(self):
        pass

def main():
    '''Process arguments and starts the Converter'''
    args = process_converter_args()
    converter = Converter()
    converter.run_conversion(args.to_convert)

if __name__ == '__main__':
    main()
