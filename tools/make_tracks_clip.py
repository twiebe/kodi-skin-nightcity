#!/usr/bin/env python3
"""Write a 60 s test clip with two audio tracks, two subtitle tracks and three chapters for the
e2e tests of the player's track panels: python tools/make_tracks_clip.py OUT.mkv (needs ffmpeg)."""
import pathlib
import subprocess
import sys
import tempfile

SRT = '1\n00:00:00,000 --> 00:01:00,000\n{}\n'
CHAPTERS = ';FFMETADATA1\n' + ''.join(
    '[CHAPTER]\nTIMEBASE=1/1000\nSTART={}\nEND={}\ntitle={}\n'.format(s * 1000, e * 1000, t)
    for s, e, t in ((0, 20, 'Opening'), (20, 40, 'Middle'), (40, 60, 'End')))


def make(out):
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        (tmp / 'de.srt').write_text(SRT.format('Untertitel deutsch'))
        (tmp / 'en.srt').write_text(SRT.format('English subtitle'))
        (tmp / 'chapters.txt').write_text(CHAPTERS)
        subprocess.run([
            'ffmpeg', '-y', '-loglevel', 'error',
            '-f', 'lavfi', '-i', 'testsrc=size=640x360:rate=25:duration=60',
            '-f', 'lavfi', '-i', 'sine=frequency=440:duration=60',
            '-f', 'lavfi', '-i', 'sine=frequency=660:duration=60',
            '-i', str(tmp / 'de.srt'), '-i', str(tmp / 'en.srt'), '-i', str(tmp / 'chapters.txt'),
            '-map', '0:v', '-map', '1:a', '-map', '2:a', '-map', '3:s', '-map', '4:s', '-map_chapters', '5',
            '-c:v', 'libx264', '-preset', 'ultrafast', '-c:a', 'aac', '-ac:a:0', '2', '-ac:a:1', '6',
            '-c:s', 'srt',
            '-metadata:s:a:0', 'language=ger', '-metadata:s:a:0', 'title=Deutsch',
            '-metadata:s:a:1', 'language=eng', '-metadata:s:a:1', 'title=English',
            '-metadata:s:s:0', 'language=ger', '-metadata:s:s:1', 'language=eng',
            str(out)], check=True)


if __name__ == '__main__':
    make(sys.argv[1])
