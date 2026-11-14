# Batch lossless WebP converter for ScreenCrawler.
#
# EN: Install Python 3 and Pillow: python -m pip install Pillow
# Run python convert_to_webp.py for interactive folder and deletion choices.
# CLI: python convert_to_webp.py --source "C:\Pictures" --output "C:\Converted"
# --delete-originals deletes eligible static originals after pixel verification.
# Animated and other unsupported deletion modes are always retained.
# Default CLI output is next to originals; existing targets are skipped.
# Subfolders are not scanned. JPEG may grow. Metadata except ICC is lost.
#
# RU: Установите Python 3 и Pillow: python -m pip install Pillow
# Запустите python convert_to_webp.py для выбора папок и удаления исходников.
# Аргументы: --source ПАПКА --output ПАПКА --delete-originals
# По умолчанию результат рядом с исходником, удаление отключено.
# Анимации и неподдерживаемые режимы исходников не удаляются.
# Существующие результаты пропускаются. Подпапки не сканируются.
# JPEG может увеличиться. Метаданные, кроме ICC, не сохраняются.

import argparse
import sys
import tempfile
from pathlib import Path
from PIL import Image, ImageOps, ImageSequence
import os

ROOT = Path(__file__).resolve().parent



def convert(source, target):
    fd, name = tempfile.mkstemp(suffix='.tmp', dir=target.parent)
    os.close(fd)
    temp = Path(name)
    try:
        with Image.open(source) as im:
            options = dict(format='WEBP', lossless=True, quality=100, method=6, exact=True)
            if im.info.get('icc_profile'):
                options['icc_profile'] = im.info['icc_profile']
            if getattr(im, 'is_animated', False):
                frames, durations = [], []
                for i, frame in enumerate(ImageSequence.Iterator(im)):
                    if i == 0 and im.info.get('default_image'):
                        continue
                    frames.append(ImageOps.exif_transpose(frame).convert('RGBA'))
                    durations.append(round(frame.info.get('duration', 100)))
                frames[0].save(temp, save_all=True, append_images=frames[1:],
                               duration=durations, loop=im.info.get('loop', 1), **options)
            else:
                frame = ImageOps.exif_transpose(im)
                frame = frame.convert('RGBA' if 'A' in frame.getbands() or 'transparency' in frame.info else 'RGB')
                frame.save(temp, **options)
        # Verify decoded pixels before publishing or deleting anything.
        with Image.open(source) as original, Image.open(temp) as result:
            expected = [ImageOps.exif_transpose(f).convert('RGBA')
                        for i, f in enumerate(ImageSequence.Iterator(original))
                        if not (i == 0 and original.info.get('default_image'))]
            actual = [f.convert('RGBA') for f in ImageSequence.Iterator(result)]
            if len(expected) != len(actual) or any(
                a.size != b.size or a.tobytes() != b.tobytes()
                for a, b in zip(expected, actual)
            ):
                raise ValueError('Decoded pixels or frame count differ')
        # Hard link publishes atomically without overwriting existing files.
        os.link(temp, target)
    finally:
        temp.unlink(missing_ok=True)


def choose_folder(prompt, default):
    while True:
        choice = input(prompt + '\n  1. ' + str(default) +
                       ' (default)\n  2. Specify another folder\n> ').strip()
        if choice in ('', '1'):
            return default
        if choice == '2':
            value = input('Folder path: ').strip().strip('"')
            if value:
                return Path(value).expanduser().resolve()


def main():
    parser = argparse.ArgumentParser(description='Batch lossless WebP converter')
    parser.add_argument('--source', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--delete-originals', action='store_true')
    args = parser.parse_args()
    source_dir = args.source.resolve()
    out = args.output.resolve() if args.output else source_dir
    delete = args.delete_originals
    if len(sys.argv) == 1:
        source_dir = choose_folder('Select image folder:', ROOT)
        out = choose_folder('Select output folder:', source_dir)
        delete = input('Delete original STATIC images after verified conversion? [y/N]: ').strip().lower() in ('y', 'yes')
    if not source_dir.is_dir():
        parser.error('Source folder does not exist')
    out.mkdir(parents=True, exist_ok=True)
    total_before = total_after = ok = errors = 0
    used = set()
    for source in sorted(source_dir.iterdir(), key=lambda p: p.name.casefold()):
        if not source.is_file() or source.suffix.lower() == '.webp':
            continue
        try:
            with Image.open(source) as im:
                fmt = im.format
                animated = getattr(im, 'is_animated', False)
                safe_delete = im.mode in ('1', 'L', 'LA', 'P', 'RGB', 'RGBA') and fmt in ('PNG', 'JPEG', 'BMP', 'GIF') and not animated
        except (OSError, ValueError):
            continue
        if fmt == 'WEBP':
            continue
        target = out / (source.stem + '.webp')
        n = 2
        while target.name.casefold() in used:
            target = out / f'{source.stem}_{n}.webp'
            n += 1
        used.add(target.name.casefold())
        if target.exists():
            print(f'SKIP {source.name}: output already exists')
            continue
        try:
            print(f'Converting {source.name} ({fmt})...', flush=True)
            convert(source, target)
            before, after = source.stat().st_size, target.stat().st_size
            print(f'  {before:,} -> {after:,} B | saving {100*(1-after/before):+.2f}%')
            total_before += before
            total_after += after
            ok += 1
            if delete and safe_delete:
                source.unlink()
                print('  Original deleted')
            elif delete:
                print('  Original retained (animated or unsupported deletion mode)')
        except Exception as exc:
            errors += 1
            print(f'  ERROR: {exc}')
    print(f'\nConverted: {ok} | errors: {errors}')
    if total_before:
        print(f'TOTAL: {total_before:,} -> {total_after:,} B | saving {100*(1-total_after/total_before):+.2f}%')
    print(f'Output: {out}')


if __name__ == '__main__':
    main()
