"""Measure screenshot differences without ignoring or editing any pixels."""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    rows = []
    for original in sorted(args.directory.glob('*-original*.png')):
        migrated = original.with_name(original.name.replace('-original', '-vue'))
        if not migrated.is_file():
            rows.append({'original': original.name, 'missing': migrated.name})
            continue
        with Image.open(original) as left, Image.open(migrated) as right:
            if left.size != right.size:
                rows.append({'original': original.name, 'size_mismatch': [left.size, right.size]})
                continue
            difference = np.abs(np.asarray(left.convert('RGB')).astype(np.int16)
                                - np.asarray(right.convert('RGB')).astype(np.int16))
        rows.append({'original': original.name,
                     'different_pixels': int(np.any(difference != 0, axis=2).sum()),
                     'pixels_above_8': int(np.any(difference > 8, axis=2).sum()),
                     'max_channel_delta': int(difference.max())})
    report_path = args.directory / 'report.json'
    comparisons = json.loads(report_path.read_text()) if report_path.is_file() else []
    modes = {row.get('comparisonMode', 'unspecified') for row in comparisons}
    comparison_mode = next(iter(modes)) if len(modes) == 1 else 'unspecified'
    result = {'comparison_mode': comparison_mode, 'screenshot_pairs': len(rows),
              'exact_pairs': sum(row.get('different_pixels') == 0 for row in rows),
              'incomplete_pairs': sum('different_pixels' not in row for row in rows),
              'note': 'All RGB differences count; pixels_above_8 is supplemental, not an equality threshold.',
              'pairs': rows}
    (args.directory / 'pixel-report.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({key: value for key, value in result.items() if key != 'pairs'}))


if __name__ == '__main__':
    main()
