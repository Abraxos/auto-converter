# Auto-Converter

A utility that can be configured to watch a set of media directories. Each media input directory would have corresponding output, done, and error directories. When a video file in placed in an input directory, it is converted to a given format and placed in an output directory. The original source file is placed in the done directory if it was properly converted, otherwise it is placed in the error directory. This utility primarily uses Twisted/iNotify to react to new files and `ffmpeg` to convert video files as needed.

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

As of right now, the program only converts to one preset format without giving the user the ability to define their own SD format. A goal of this script would be to allow the user to define the standard format and quality to convert to for each directory. Another useful feature is to either write this to function as a service/daemon, or to use termbox and display nice-looking progress bars, or both.

## Installation/Usage

To install the program, simply clone the git repo, for the purposes of this, we will say that its in `/home/user/Repos/auto-converter/` and do the following:

```
$ sudo apt install ffmpeg mediainfo
$ wget https://bootstrap.pypa.io/get-pip.py
$ sudo python3 get-pip.py
$ rm get-pip.py
$ sudo pip3 install twisted
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

As of right now it simply runs inside the shell and not as a daemon or service of any kind. I am considering how to set this up with sufficiently good logging so that I can view what's going on but not have to keep the shell open. For now, if you want to just keep running this consider using a program like Screen or Tmux.

I personally use Tmux, and you can rather easily set up a session like so:

```
$ tmux new-session -s auto-converter
```

A new session will be created and your shell will be attached to it automatically, now you can launch auto-converter

```
$ auto-converter /path/to/your/config.ini
```

Now you can exit from the terminal, or just detach from the session (`[Ctrl] + B`, `D`) and auto-converter will keep running inside the tmux session. You can re-attach to the session by executing:

```
$ tmux attach-session -t auto-converter
```
