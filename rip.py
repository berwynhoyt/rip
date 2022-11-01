#!/usr/bin/env python3

""" Usage: python rip.py <source_file> [output_path] """

#edit the following if you wish to change them
handbrake = "HandBrakeCLI"
minimum_seconds = 60*3

# Logfiles will go in the output_path
logfile = 'rip.log'
handbrakelog = 'handbrake.log'

import sys
import os
import subprocess
import re
import collections
import glob
import datetime

output_path = ''

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

def scan(source):
    """ Find titles in input source and return a dict of titles with fields '1', '2', '3', ...
        with each field's value a duration object with fields 'seconds' and 'text' (for human-readable time).
        If there is a line "DVD Title: <name>" in the source scan, include it as a field 'title' in the dict.
    """
    lines = capture_shell(handbrake, '-t0', '-i', source).stderr
    Duration = collections.namedtuple('duration', 'seconds text')
    titles = {}
    for line in lines:
        istitle = re.search(r"\+ title ([0-9]+):", line)
        if istitle:
            title = istitle[1]
        isduration = re.search(r"\+ duration: (([0-9]{2}):([0-9]{2}):([0-9]{2}))", line)
        if isduration:
            duration_text = isduration[1]
            hh, mm, ss = int(isduration[2]), int(isduration[3]), int(isduration[4])
            duration_seconds = hh*3600 + mm*60 + ss
            titles[title] = Duration(duration_seconds, duration_text)
        isdvdtitle = re.search(r"DVD Title: (.*)", line)
        if isdvdtitle:
            titles['title'] = isdvdtitle[1]
    return titles

def rip(source, dest, minimum_seconds=60*3):
    """ Find titles in input source and rip them if they are longer than seconds duration """
    titles = scan(source)
    if not titles:
        printlog(f"ERROR: No titles found in {source} -- skipping")
        return

    included = []
    for title, duration in titles.items():
        include = duration.seconds >= minimum_seconds
        print(f"Title {title} ({duration.text})" + ("" if include else f" -- skipped because < {minimum_seconds}s"))
        if include: included.append(title)

    included.sort(key=lambda title: titles[title].seconds, reverse=True)
    print("\nSmallest titles first:")
    for title in included:
        duration = titles[title]
        dest += f"-{int(title):02}.m4v"
        printlog(f"Ripping title {int(title):02} ({duration.text}) as {dest}")
        args = [handbrake, f"-t{title}", '--markers', '--optimize', '-i', source, '-o', dest]
        args.append(f"2>>{handbrakelog}")
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S ')
        with open(handbrakelog, 'a') as hlog:
            print('\n' + timestamp + ' '.join(args), file=hlog)
        process_info = subprocess.run(args, shell=True)

def glob_rip(source, minimum_seconds=60*3):
    """ Expand wildcards in source and rip() all matching files """
    for filename in glob.glob(source):
        basename, ext = os.path.splitext(filename)
        dest = basename
        if output_path and not filename[0] not in r"\/":
            dest = os.path.join(output_path, filename)

        printlog(f"Ripping {filename}")
        rip(filename, dest, minimum_seconds)
        print()


if __name__ == "__main__":
    source = sys.argv[1]
    if len(sys.argv) > 2:
        output_path = sys.argv[2]
        logfile = os.path.join(output_path, logfile)
        handbrakelog = os.path.join(output_path, handbrakelog)

    try:
        glob_rip(source, minimum_seconds)
    except KeyboardInterrupt:
        print("User interrupted process", file=sys.stderr)
