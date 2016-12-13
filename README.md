# Auto-Converter

A utility that can be configured with a set of directory pairs. Each pair contains an input directory and an output directory. When a video file in placed in an input directory, it is converted to a given format and placed in an output directory. This utility primarily uses Twisted/iNotify to react to new files and `ffmpeg` to convert video files as needed. It should soon be written to use termbox to display nice-looking progress bars.

## Development Setup

This project should be developed inside of a python virtualenv which means that you should install `virtualenvwrapper` and several other utilities required to build some of the packages.

```
$ sudo apt install virtualenvwrapper python3-dev build-essential mediainfo
```

Then you need to install pip for Python 3:

```
$ wget https://bootstrap.pypa.io/get-pip.py
$ sudo python3 get-pip.py
$ rm get-pip.py
```

Then you want to use `virtualenvwrapper` to create the development environment for auto-converter (if you just installed `virtualenvwrapper` you may need to close and open your terminal again or use the `reset` command):

```
$ mkvirtualenv -p /usr/bin/python3 auto-converter
(auto-converter) $
```

From now on, all commands in this document that are supposed to be executed from the virtual environment will be prefaced with `(auto-converter) $` whereas any commands that should be executed outside of a virtual environment as a normal user will be prefaced with just `$` (root user commands will be prefaced with `#`).

Inside the virtual environment you need to install the following python packages:

```
(auto-converter) $ pip install twisted
```

## Upcoming Features

As of right now, the program only converts to one preset format without giving the user the ability to define their own SD format. A goal of this script would be to allow the user to define the standard format and quality to convert to for each directory.

## Installation/Usage

To install the program, simply clone the git repo, for the purposes of this, we will say that its in `/home/user/Repos/auto-converter/` and do the following:

```
$ sudo apt install ffmpeg mediainfo
$ wget https://bootstrap.pypa.io/get-pip.py
$ sudo python3 get-pip.py
$ rm get-pip.py
$ pip3 install twisted
```

Once the pre-requisites are installed, you need to symlink the script to a directory in your path. For example:

```
$ sudo ln -s /home/user/Repos/auto-converter/auto_converter.py /usr/local/bin/auto-converter
```

### Usage

Now to use the program, simply set up your configuration file (see examples directory) and then execute:

```
$ auto-converter /path/to/your/config.ini
```
