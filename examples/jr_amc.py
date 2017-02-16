#!/usr/bin/python
import os
import string
import multiprocessing
import subprocess
import signal
import sys

from jr_config import *
from jr_fsutils import *
from jr_mediadb import *
from jra_utils import *

# Estimates the value of a bitrate based on the closest to a predefined value
def estimateBR(br):
    bitrates = [56,64,80,96,112,128,160,192]
    if br in bitrates: return br
    elif br < 56: return 56
    elif br > 192: return 192
    else: return min(bitrates, key=lambda x:abs(x-br))


# Returns the best audio bitrate given the media information
def audio_bitrate_str(mi):
    if "Bit rate" in mi.audio_properties:
        r = '192k'
        try:
            r = str(estimateBR(int(float(mi.audio_properties["Bit rate"].replace(' ','')[:-4])))) + 'k'
        except:
            return '192k'
        return r
    else:
        return '192k'


# return the best video resolution string based on existing media information
def resolution_str(mi):
    all = string.maketrans('','')
    nodigits = all.translate(all,string.digits)
    height = mi.getPixelHeight() if mi.getPixelHeight() < 640 else 640
    width = mi.getPixelWidth() if mi.getPixelWidth() < 1136 else 1136
    return str(width) + 'x' + str(height)


def convert(src,dst_path,vfdb,cnvr=None,c=True,result = {}):

    def converted(cnvr,new_mi,converted_time,result):
        print('')
        vfdb.mark_record_converted(cnvr,converted_time)
        result['conversion success'] = True

    def not_converted(cnvr,converted_time,result):
        print("POST CONVERSION ERROR: Unable to read media info from produced "
              "file")
        vfdb.mark_record_unconverted(cnvr,converted_time)
        result['conversion success'] = False

    src_path = src.src_path
    src_mi = MediaInfo().load_from_file(src_path)

    if src_mi.valid():
        # create the conversion record
        if not cnvr: cnvr = vfdb.new_conversion_record(src_path,dst_path)

        # get the required values
        abr = audio_bitrate_str(src_mi)
        res = resolution_str(src_mi)
        old_res = src_mi.getResolutionStr()
        old_abr = None if "Bit rate" not in src_mi.audio_properties else src_mi.audio_properties["Bit rate"]
        old_size = src_mi.general_properties["File size"]
        converted_time = datetime.datetime.now()

        print(path_leaf(src_path) +" ABR: " + str(old_abr) + " RES: " + old_res +
              " SIZE: " + old_size + " ~> " + path_leaf(dst_path) + " ABR: " +
              abr + " RES: " + res)

        # convert, check if successful, mark as such
        if c:
            call(['avconv','-stats','-v','3','-y','-i',src_path,'-acodec',
                  'ac3','-ab',abr,'-c:v','libx264','-crf','23','-s:v',res,
                  dst_path])
            try:
                new_mi = MediaInfo().load_from_file(dst_path)
                if new_mi.valid():
                    converted(cnvr,new_mi,converted_time,result)
                else:
                    not_converted(cnvr,converted_time,result)
            except:
                not_converted(cnvr,converted_time,result)
        else:
            converted(cnvr,None,converted_time,result)
    else:
        result['conversion success'] = False


def human_readable_size(size_b):
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
    return '%.2f %s' % (size_float,size_unit)


def avconv_pid():
    try:
        ps_command = subprocess.Popen("ps aux | grep avconv",
                                      shell=True,
                                      stdout=subprocess.PIPE)
        ps_output = ps_command.stdout.read()
        retcode = ps_command.wait()
        for line in ps_output.split('\n'):
            if 'grep' not in line:
                linedata = re.split(r'\s+', line)
                return int(linedata[1])
    except:
        return 0


def get_proc_fd_pos(pid,filepath):
    fd_info = None
    fd_num = None
    filepath = os.path.realpath(filepath)
    proc_dir = '/proc/' + str(pid) + '/fd'
    if os.path.isdir(proc_dir):
        for fd_symlink in os.listdir(proc_dir):
            if os.path.realpath(os.path.join(proc_dir,fd_symlink)) == filepath:
                fd_num = fd_symlink
                break
    pos = 0
    if fd_num:
        with open(proc_dir + 'info/' + fd_num,'r') as fd_info_file:
            pos = int(fd_info_file.readline()[:-1].split('\t')[1])
    return pos


def convert_with_progress(src,dst_path,vfdb,cnvr=None,c=True):
    manager = Manager()
    return_dict = manager.dict()
    p = multiprocessing.Process(target=convert,
                                args=(src,dst_path,vfdb,cnvr,c,return_dict))
    p.start()
    p_string = ''
    size = os.stat(src.src_path).st_size
    time.sleep(2)
    while p.is_alive():
        if os.path.isfile(dst_path):
            pid = avconv_pid()
            outputinfo = os.stat(dst_path)
            if pid:
                pos = get_proc_fd_pos(pid, src.src_path)
            else:
                pos = size

            print('\b' * (len(p_string) + 2)),
            print(' ' * (len(p_string))),
            print('\b' * (len(p_string) + 2)),
            p_string = ("PROGRESS: OUTPUT_SIZE: %s PROCESSED: %s / %s COMPLETE"
                        ": %.2f%% RATE: ??ps ETA: ??s") % (
                        human_readable_size(outputinfo.st_size),
                        human_readable_size(pos),human_readable_size(size),
                        float(pos)/float(size) * 100.0)
            print(p_string),
            sys.stdout.flush()
            time.sleep(2)
    p.join()
    return return_dict['conversion success']


class MediaConverter(object):

    def __init__(self,source,destination,error,temp,media_type,db_location):
        self.source = source
        self.destination = destination
        self.error = error
        self.temp = temp
        self.media_type = media_type
        self.f_list = []
        self.db_location = db_location
        self.db = VideoFileDatabase(self.db_location)
        self.db.construct()
        # TODO: Need to change this program to use the new JRMediaFile/DB objects

        self.f_list = generate_file_objects(self.source,self.media_type,self.db)

    def run(self,c=True):
        self.num_total_files = len(self.f_list)
        self.num_converted_files = 0
        self.num_ignored_files = 0
        self.num_previously_converted_files = 0

        def stat():
            print("\n" + str(self.num_converted_files +
                  self.num_ignored_files +
                  self.num_previously_converted_files) +
                  "/" + str(self.num_total_files)),

        c_list = []
        for f in self.f_list:
            try:
                conr = self.db.get_conversion_record(f)
            except:
                log("ERROR CONVERTING: " + f.src_path)
                continue
            dst_path = os.path.join(self.destination,filename(f.src_path)) + ".mp4"

            if conr:
                ext_mi = MediaInfo()
                ext_mir = self.db.get_mediainfo_record(conr.src_file_path)
                ext_mi.load_from_db(self.db,ext_mir.src_file_path)
                # get the media info of the new file
                new_mi = MediaInfo()
                new_mi.load_from_file(f.src_path)
                if conr.converted:
                    if (new_mi > ext_mi):
                        stat()
                        print("CONVERTING (Higher Quality):")
                        self.db.update_mediainfo_record(ext_mir,new_mi)
                        self.num_converted_files += 1
                        if convert_with_progress(f,dst_path,self.db,conr,c):
                            c_list.append(path_leaf(f.src_path))
                    elif new_mi == ext_mi and (conr.converted_time < f.mtime and f.mtime < datetime.datetime.now()):
                        stat()
                        print("CONVERTING (Updated Source):")
                        self.num_converted_files += 1
                        if convert_with_progress(f,dst_path,self.db,conr,c):
                            c_list.append(path_leaf(f.src_path))
                    elif new_mi == ext_mi and conr.converted_time >= f.mtime:
                        self.num_previously_converted_files += 1
                        stat()
                        print("CONVERTED: " + path_leaf(f.src_path))
                    elif new_mi < ext_mi:
                        self.num_ignored_files += 1
                        stat()
                        print("IGNORED: " + path_leaf(f.src_path))
                elif not conr.converted:
                    self.num_converted_files += 1
                    stat()
                    if convert_with_progress(f,dst_path,self.db,conr,c):
                        c_list.append(path_leaf(f.src_path))
            else:
                # create a mediainfo record
                mi = MediaInfo().load_from_file(f.src_path)
                # insert it into the database
                mir = mi.to_record()
                self.db.session.add(mir)
                self.db.session.commit()
                # convert the file
                self.num_converted_files += 1
                stat()
                if convert_with_progress(f,dst_path,self.db,conr,c):
                    c_list.append(path_leaf(f.src_path))
        print("CONVERTED: "
              + str(self.num_converted_files)
              + " CONVERTED PREVIOUSLY: "
              + str(self.num_previously_converted_files)
              + " IGNORED: "
              + str(self.num_ignored_files)
              + " TOTAL: "
              + str(self.num_total_files))
        return c_list


def main():
    log("Starting Jolly Roger - Automated Media Conversion")
    if not currently_running(__file__):
        movie_converter = MediaConverter(MOVIE_DESTINATION_DIR,
                                         MOVIE_CONVERSION_DIR,
                                         MOVIE_ERROR_DIR,
                                         MOVIE_TEMP_DIR,
                                         Media.Movie,
                                         CONVERSION_DB_LOCATION)
        movie_converter.run()
        tv_converter = MediaConverter(TV_DESTINATION_DIR,
                                      TV_CONVERSION_DIR,
                                      TV_ERROR_DIR,
                                      TV_TEMP_DIR,
                                      Media.Episode,
                                      CONVERSION_DB_LOCATION)
        tv_converter.run()
    else:
        log("Another instance of this program is already running.")
    log("Done!")


if __name__ == "__main__":
    main()
