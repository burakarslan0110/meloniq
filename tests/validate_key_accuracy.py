#!/usr/bin/env python3
"""
Key Detection Accuracy Validation Script.

This script validates key detection accuracy on real audio files.
It can download audio from YouTube or use local files.

Usage:
    # With local file
    python validate_key_accuracy.py path/to/audio.mp3 "F# Major"

    # With YouTube URL
    python validate_key_accuracy.py https://www.youtube.com/watch?v=VIDEO_ID "F# Major"

    # Batch validation from CSV
    python validate_key_accuracy.py --batch test_cases.csv

CSV format:
    audio_path,expected_key
    path/to/song1.mp3,F# Major
    https://www.youtube.com/watch?v=xyz,D Minor
"""

import argparse
import csv
import sys
import tempfile
from pathlib import Path
from typing import Optional, Tuple

import librosa
import numpy as np

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from meloniq.analysis.key import KeyAnalyzer


def download_youtube_audio(url: str, output_path: Optional[Path] = None) -> Path:
    """
    Download audio from YouTube URL.

    Args:
        url: YouTube video URL
        output_path: Optional output path, otherwise uses temp file

    Returns:
        Path to downloaded audio file
    """
    try:
        import yt_dlp
    except ImportError:
        print("ERROR: yt-dlp not installed. Install with: pip install yt-dlp")
        sys.exit(1)

    if output_path is None:
        temp_dir = Path(tempfile.mkdtemp())
        output_path = temp_dir / "audio.mp3"

    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': str(output_path.with_suffix('')),
        'quiet': True,
        'no_warnings': True,
    }

    print(f"Downloading audio from YouTube...")
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    # yt-dlp adds .mp3 extension
    actual_path = output_path.with_suffix('.mp3')
    if not actual_path.exists():
        # Try without extension modification
        actual_path = output_path

    if not actual_path.exists():
        raise FileNotFoundError(f"Downloaded file not found at {actual_path}")

    print(f"Downloaded to: {actual_path}")
    return actual_path


def load_audio(audio_path: str) -> Tuple[np.ndarray, int]:
    """
    Load audio file.

    Args:
        audio_path: Path to audio file or YouTube URL

    Returns:
        Tuple of (audio samples, sample rate)
    """
    if audio_path.startswith('http://') or audio_path.startswith('https://'):
        # Download from YouTube
        audio_file = download_youtube_audio(audio_path)
    else:
        audio_file = Path(audio_path)
        if not audio_file.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_file}")

    print(f"Loading audio: {audio_file}")
    y, sr = librosa.load(str(audio_file), sr=22050, mono=True)

    return y, sr


def normalize_key(key: str) -> str:
    """
    Normalize key string for comparison.

    Handles:
    - Case variations (F# major vs F# Major)
    - Enharmonic equivalents (C# vs Db)
    - Space/hyphen variations
    """
    key = key.strip().lower()

    # Normalize sharps/flats
    enharmonic_map = {
        'c#': 'db',
        'd#': 'eb',
        'f#': 'gb',
        'g#': 'ab',
        'a#': 'bb',
    }

    # Get root and mode
    parts = key.split()
    if len(parts) != 2:
        return key

    root, mode = parts

    # Check if root has enharmonic equivalent
    if root in enharmonic_map:
        # Return both versions for comparison
        return key

    return key


def keys_match(detected: str, expected: str) -> bool:
    """
    Check if detected key matches expected key.

    Accounts for enharmonic equivalents.
    """
    detected = detected.lower().strip()
    expected = expected.lower().strip()

    if detected == expected:
        return True

    # Check enharmonic equivalents
    enharmonic_pairs = [
        ('c# major', 'db major'),
        ('c# minor', 'db minor'),
        ('d# major', 'eb major'),
        ('d# minor', 'eb minor'),
        ('f# major', 'gb major'),
        ('f# minor', 'gb minor'),
        ('g# major', 'ab major'),
        ('g# minor', 'ab minor'),
        ('a# major', 'bb major'),
        ('a# minor', 'bb minor'),
    ]

    for key1, key2 in enharmonic_pairs:
        if (detected == key1 and expected == key2) or \
           (detected == key2 and expected == key1):
            return True

    return False


def validate_single(audio_path: str, expected_key: str, verbose: bool = True) -> dict:
    """
    Validate key detection on a single audio file.

    Args:
        audio_path: Path to audio file or YouTube URL
        expected_key: Expected key (e.g., "F# Major")
        verbose: Print detailed output

    Returns:
        Dictionary with validation results
    """
    if verbose:
        print(f"\n{'='*60}")
        print(f"Audio: {audio_path}")
        print(f"Expected Key: {expected_key}")
        print(f"{'='*60}\n")

    try:
        # Load audio
        y, sr = load_audio(audio_path)
        duration = len(y) / sr

        if verbose:
            print(f"Duration: {duration:.1f}s")
            print(f"Sample Rate: {sr} Hz")

        # Analyze key
        analyzer = KeyAnalyzer()
        result = analyzer.analyze(y, sr)

        detected_key = result.global_key
        confidence = result.confidence
        is_correct = keys_match(detected_key, expected_key)

        if verbose:
            print(f"\nDetected Key: {detected_key}")
            print(f"Confidence: {confidence:.2%}")
            print(f"Match: {'✓ CORRECT' if is_correct else '✗ INCORRECT'}")

            if result.alternatives:
                print(f"\nAlternatives:")
                for i, alt in enumerate(result.alternatives[:3], 1):
                    match_marker = ' ← Expected' if keys_match(alt.key, expected_key) else ''
                    print(f"  {i}. {alt.key} ({alt.confidence:.2%}){match_marker}")

            if hasattr(result, 'vocal_detected'):
                print(f"\nVocal Detected: {result.vocal_detected}")

            print(f"\n{result.explanation}")

        return {
            'audio_path': audio_path,
            'expected_key': expected_key,
            'detected_key': detected_key,
            'confidence': confidence,
            'is_correct': is_correct,
            'expected_in_alternatives': any(
                keys_match(alt.key, expected_key)
                for alt in result.alternatives
            ) if result.alternatives else False,
        }

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return {
            'audio_path': audio_path,
            'expected_key': expected_key,
            'detected_key': None,
            'confidence': 0.0,
            'is_correct': False,
            'expected_in_alternatives': False,
            'error': str(e),
        }


def validate_batch(csv_path: str) -> None:
    """
    Validate multiple audio files from CSV.

    Args:
        csv_path: Path to CSV file with columns: audio_path, expected_key
    """
    csv_file = Path(csv_path)
    if not csv_file.exists():
        print(f"ERROR: CSV file not found: {csv_file}")
        sys.exit(1)

    results = []

    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for row in reader:
            audio_path = row.get('audio_path', '').strip()
            expected_key = row.get('expected_key', '').strip()

            if not audio_path or not expected_key:
                print(f"Skipping invalid row: {row}")
                continue

            result = validate_single(audio_path, expected_key, verbose=True)
            results.append(result)

    # Print summary
    print(f"\n{'='*60}")
    print("BATCH VALIDATION SUMMARY")
    print(f"{'='*60}\n")

    correct = sum(1 for r in results if r.get('is_correct', False))
    total = len(results)
    accuracy = correct / total if total > 0 else 0

    print(f"Total: {total}")
    print(f"Correct: {correct}")
    print(f"Incorrect: {total - correct}")
    print(f"Accuracy: {accuracy:.2%}\n")

    # Show incorrect detections
    incorrect = [r for r in results if not r.get('is_correct', False)]
    if incorrect:
        print("Incorrect Detections:")
        for r in incorrect:
            print(f"  {r['audio_path']}")
            print(f"    Expected: {r['expected_key']}")
            print(f"    Detected: {r['detected_key']} ({r['confidence']:.2%})")
            if r.get('expected_in_alternatives'):
                print(f"    Note: Expected key found in alternatives")
            print()


def main():
    parser = argparse.ArgumentParser(
        description="Validate key detection accuracy on audio files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate local file
  python validate_key_accuracy.py song.mp3 "F# Major"

  # Validate YouTube video
  python validate_key_accuracy.py "https://www.youtube.com/watch?v=RjOfwJjAGsg" "F# Major"

  # Batch validation from CSV
  python validate_key_accuracy.py --batch test_cases.csv

Test Case for Issue (F# Major vocal song):
  python validate_key_accuracy.py "https://www.youtube.com/watch?v=RjOfwJjAGsg" "F# Major"
        """
    )

    parser.add_argument(
        'audio_path',
        nargs='?',
        help='Path to audio file or YouTube URL'
    )

    parser.add_argument(
        'expected_key',
        nargs='?',
        help='Expected key (e.g., "F# Major")'
    )

    parser.add_argument(
        '--batch',
        help='Path to CSV file for batch validation'
    )

    args = parser.parse_args()

    if args.batch:
        validate_batch(args.batch)
    elif args.audio_path and args.expected_key:
        result = validate_single(args.audio_path, args.expected_key, verbose=True)

        # Exit with error code if incorrect
        if not result.get('is_correct', False):
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
