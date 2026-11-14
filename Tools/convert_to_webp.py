# Batch lossless WebP converter for ScreenCrawler.
#
# EN: Install Python 3 and Pillow: python -m pip install Pillow
# Place this script next to your images and run: python convert_to_webp.py
# Converted files appear in the WebP subfolder. Originals are unchanged.
# Existing output files may be overwritten. Subfolders are not scanned.
# JPEG inputs may grow in size. Metadata other than ICC is not preserved.
#
# RU: Установите Python 3 и Pillow: python -m pip install Pillow
# Поместите скрипт в папку с изображениями и запустите: python convert_to_webp.py
# Результаты появятся в подпапке WebP. Исходники не изменяются.
# Существующие результаты могут быть перезаписаны. Подпапки не сканируются.
# JPEG может увеличиться в размере. Метаданные, кроме ICC, не сохраняются.

from pathlib import Path
from PIL import Image, ImageOps, ImageSequence
import os

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'WebP'
OUT.mkdir(exist_ok=True)


def convert(source, target):
    temp = target.with_suffix('.tmp')
    try:
        with Image.open(source) as im:
            options = dict(format='WEBP', lossless=True, quality=100, method=6, exact=True)
            if im.info.get('icc_profile'):
                options['icc_profile'] = im.info['icc_profile']
            if getattr(im, 'is_animated', False):
                frames, durations = [], []
                for frame in ImageSequence.Iterator(im):
                    frames.append(ImageOps.exif_transpose(frame).convert('RGBA'))
                    durations.append(round(frame.info.get('duration', 100)))
                frames[0].save(temp, save_all=True, append_images=frames[1:],
                               duration=durations, loop=im.info.get('loop', 1), **options)
            else:
                frame = ImageOps.exif_transpose(im)
                frame = frame.convert('RGBA' if 'A' in frame.getbands() or 'transparency' in frame.info else 'RGB')
                frame.save(temp, **options)
        os.replace(temp, target)
    finally:
        temp.unlink(missing_ok=True)


def main():
    total_before = total_after = ok = errors = 0
    used = set()
    for source in sorted(ROOT.iterdir(), key=lambda p: p.name.casefold()):
        if not source.is_file() or source.suffix.lower() == '.webp':
            continue
        try:
            with Image.open(source) as im:
                fmt = im.format
        except (OSError, ValueError):
            continue
        if fmt == 'WEBP':
            continue
        target = OUT / (source.stem + '.webp')
        n = 2
        while target.name.casefold() in used:
            target = OUT / f'{source.stem}_{n}.webp'
            n += 1
        used.add(target.name.casefold())
        try:
            print(f'Converting {source.name} ({fmt})...', flush=True)
            convert(source, target)
            before, after = source.stat().st_size, target.stat().st_size
            print(f'  {before:,} -> {after:,} B | saving {100*(1-after/before):+.2f}%')
            total_before += before
            total_after += after
            ok += 1
        except Exception as exc:
            errors += 1
            print(f'  ERROR: {exc}')
    print(f'\nConverted: {ok} | errors: {errors}')
    if total_before:
        print(f'TOTAL: {total_before:,} -> {total_after:,} B | saving {100*(1-total_after/total_before):+.2f}%')
    print(f'Output: {OUT}')


if __name__ == '__main__':
    main()
