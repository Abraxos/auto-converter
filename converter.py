from os.path import splitext, getsize
from os import rename, remove
import sys
from time import sleep
from multiprocessing import Process, Manager
from subprocess import check_call, SubprocessError
from aenum import IntEnum
import psutil
from mediainfo import MediaInfo
from utils import process_converter_args, human_readable_size, percentage

ConversionStatus = IntEnum('ConversionStatus', 'NONE RUNNING PAUSED STOPPED ERROR DONE')

class Conversion(object):
    def __init__(self, src_file_path, dst_file_path, log_file_path):
        self.src = src_file_path
        self.dst = dst_file_path
        self.log = log_file_path
        self.info = MediaInfo(self.src)
        self.audio_bitrate = self.info.abr()
        self.height = self.info.video_height()
        self.width = self.info.video_width()
        self.agent = None
        self.agent_result = None
        self.agent_info = None
        self.ffmpeg_proc = None
        self.ffmpeg_proc_info = None
    def _execute(self, return_dict):
        with open(self.log, 'w+') as log_file:
            try:
                check_call(self._cmd(), stderr=log_file, stdout=log_file)
            except SubprocessError as conversion_error:
                return_dict['error'] = conversion_error
    def start(self):
        '''Starts the conversion subprocess'''
        print("Converting {} to: {}x{} Bit-Rate: {}"\
              .format(self.src, self.width, self.height, self.audio_bitrate))
        manager = Manager()
        self.agent_result = manager.dict()
        self.agent = Process(target=self._execute, args=(self.agent_result,))
        self.agent.start()
        self.agent_info = psutil.Process(self.agent.pid)
        sleep(0.5)
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
    def progress(self):
        '''Returns a float representing the conversion progress as a percentage'''
        return self.position() / self.input_size()
    def position(self):
        '''Returns the position in the input file which is a measure of progress'''
        input_file = self.ffmpeg_proc_info.open_files()[-2]
        return input_file.position
    def input_size(self):
        '''Returns the size of the input file'''
        return getsize(self.src)
    def output_size(self):
        '''Returns the size of the output file'''
        output_file = self.ffmpeg_proc_info.open_files()[-1]
        return output_file.position
    def state(self):
        '''Returns the status of the FFMPEG conversion process'''
        return self.ffmpeg_proc_info.status()
    def result(self):
        return self.agent_result
    def _cmd(self):
        '''Generates a conversion command'''
        cmd = ['ffmpeg', '-stats', '-y', '-i', self.src, '-s:v',
               str(self.width) + 'x' + str(self.height)]
        cmd.extend(['-acodec', 'mp3', '-ab', self.audio_bitrate] \
                    if self.audio_bitrate else ['-acodec', 'copy'])
        cmd.extend(['-c:v', 'libx264', self.dst])
        return cmd

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
        self.conversion = Conversion(src_file_path, dst_file_path, log_file_path)
        self.conversion.start()
        while True:
            try:
                output_str = "Conversion ouput: {} Progress {}      \r".format(human_readable_size(self.conversion.output_size()), percentage(self.conversion.progress()))
                sys.stdout.write(output_str)
                sleep(1)
                sys.stdout.flush()
            except psutil.NoSuchProcess:
                print("Conversion process ended...")
                break
        result = self.conversion.result()
        if 'error' in result:
            print("There was an error during conversion: {}".format(result))
        elif getsize(dst_file_path) < 10000:
            print("There was an error during conversion: {} is too small...".format(dst_file_path))
        else:
            remove(src_file_path)
            rename(dst_file_path, final_dst_file_path)
    def status(self):
        pass

def main():
    '''Process arguments and starts the Converter'''
    args = process_converter_args()
    converter = Converter()
    converter.run_conversion(args.to_convert)

if __name__ == '__main__':
    main()
