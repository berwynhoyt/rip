#!/usr/bin/env python3

""" Usage: python rip.py [-|-s] <source_file> [output_path]
  where -d means dry-run (i.e. show what it would have done)
        -s means small (60% of the size and slightly lower quality)
"""

#edit the following if you wish to change them
handbrake = "HandBrakeCLI"
minimum_seconds = 60*1

# Logfiles will go in the Output_path
logfile = 'rip.log'
handbrakelog = 'handbrake.log'

# The following are added after the appropriate preset (i.e. 'HQ 480p30 Surround' -- see table below)
Handbrake_options = ['--optimize']  # web optimize (directory at start of file)

# table of DVD sizes mapping to the appropriate preset
Presets_HQ = {
    480: 'HQ 480p30 Surround',
    576: 'HQ 576p25 Surround',
    720: 'HQ 720p30 Surround',
    1080: 'HQ 1080p30 Surround',
}

Presets_LQ = {
    480: 'Fast 480p30',
    576: 'Fast 576p25',
    720: 'Fast 720p30',
    1080: 'Fast 1080p30',
}

Presets = None  # set to Presets_HQ below unless -s option is supplied

import sys
import os
import subprocess
import re
from types import SimpleNamespace
import glob
import datetime

Output_path = ''

def log(string):
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S ')
    with open(logfile, 'a') as log:
        print(timestamp+string, file=log)
def printlog(string, printer=sys.stdout):
    print(string, file=printer)
    log(string)

def to_utf8(input):
    output = ''
    try:
        output = input.decode('utf-8')
    except UnicodeDecodeError:
        log(f"WARNING: Could not decode as utf-8: {input}")
    return output

def capture_shell(*args):
    """ Run subprocess specified by command line args
        Return process_info object with output in .stdout .stderr
    """
    process_info = subprocess.run(args, capture_output=True)
    process_info.stdout = [to_utf8(line) for line in process_info.stdout.strip(b'\n').split(b'\n')]
    process_info.stderr = [to_utf8(line) for line in process_info.stderr.strip(b'\n').split(b'\n')]
    return process_info

def scan(source, dry_run=False):
    """ Find numbered titles in input source and return a dict of titles with fields 1, 2, 3, ...
        with each field's value a duration object with fields 'seconds' and 'text' (for human-readable time).
        If there is a line "DVD Title: <name>" in the source scan, include it as a field 'dvdtitle' in the dict.
    """
    args = [handbrake, '-t0', '-i', source]
    if dry_run:
        print(f"Scanning {source} using: {' '.join(args)}")
    lines = capture_shell(*args).stderr
    titles = {}
    for line in lines:
        istitle = re.search(r"\+ title ([0-9]+):", line)
        if istitle:
            title = int(istitle[1])
            titles[title] = SimpleNamespace(title=title)
        isduration = re.search(r"\+ duration: (([0-9]{2}):([0-9]{2}):([0-9]{2}))", line)
        if isduration:
            duration_text = isduration[1]
            hh, mm, ss = int(isduration[2]), int(isduration[3]), int(isduration[4])
            duration_seconds = hh*3600 + mm*60 + ss
            titles[title].seconds, titles[title].text = duration_seconds, duration_text
        issize = re.search(r"\+ size: [0-9]+x([0-9]+)", line)
        if issize:
            titles[title].size = int(issize[1])
        isdvdtitle = re.search(r"DVD Title: (.*)", line)
        if isdvdtitle:
            titles['dvdtitle'] = isdvdtitle[1]
    return titles

def rip(source, dest, minimum_seconds=0, dry_run=False):
    """ Find titles in input source and rip them to "<dest>-<title>.m4v"
        but only if they are longer than seconds duration
        If dry_run is True, don't actually do the rip; just show what it would do
    """
    titles = scan(source, dry_run=dry_run)
    if not titles:
        printlog(f"ERROR: No titles found in {source} -- skipping")
        return

    included = []
    for title in titles.values():
        include = title.seconds >= minimum_seconds
        print(f"Title {title} ({title.text})" + ("" if include else f" -- skipped because < {minimum_seconds}s"))
        if include: included.append(title)

    included.sort(key=lambda title: title.seconds)
    print("\nSmallest titles first:")
    for title in included:
        outfile = dest + f"-{title.seconds//60:03}m-{title.title:02}.m4v"
        printlog(f"Ripping title {title.title:02} ({title.text}) as '{outfile}'")
        args = [handbrake, f"-t{title.title}", '-Z', Presets[title.size], *Handbrake_options, '-i', source, '-o', outfile]
        args.append(f"2>>{handbrakelog}")
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S ')
        with open(handbrakelog, 'a') as hlog:
            print('\n' + timestamp + ' '.join(args), file=hlog)
        if dry_run:
            print('  ' + ' '.join(args))
        else:
            process_info = subprocess.run(args, shell=True)

def glob_rip(source, minimum_seconds=0, dry_run=False, output_path=None):
    """ Expand wildcards in source and rip() all matching files
        If dry_run is True, don't actually do the rip; just show what it would do
    """
    for filename in glob.glob(source):
        basename, ext = os.path.splitext(filename)
        directory = basename
        if output_path and filename[0] not in r"\/":
            directory = os.path.join(output_path, directory)
        os.makedirs(directory, exist_ok=True)
        dest = os.path.join(directory, basename)
        printlog(f"Ripping {filename}")
        rip(filename, dest, minimum_seconds=minimum_seconds, dry_run=dry_run)
        print()


if __name__ == "__main__":
    dry_run = False
    Presets = Presets_HQ
    if '-d' in sys.argv:
        sys.argv.remove('-d')
        dry_run = True
    if '-s' in sys.argv:
        sys.argv.remove('-s')
        presets = Presets_LQ

    source = sys.argv[1]
    if len(sys.argv) > 2:
        Output_path = sys.argv[2]
        logfile = os.path.join(Output_path, logfile)
        handbrakelog = os.path.join(Output_path, handbrakelog)

    try:
        glob_rip(source, minimum_seconds, output_path=Output_path, dry_run=dry_run)
    except KeyboardInterrupt:
        print("User interrupted process", file=sys.stderr)
