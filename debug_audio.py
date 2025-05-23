#!/usr/bin/env python3
"""
Audio Quality Comparison Tool
Check audio levels and quality of exported files
"""

import numpy as np
import wave
import argparse
from pathlib import Path

def analyze_audio_file(file_path):
    """Analyze audio file for quality metrics"""
    try:
        with wave.open(str(file_path), 'rb') as wav_file:
            # Get audio properties
            sample_rate = wav_file.getframerate()
            num_channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            num_frames = wav_file.getnframes()
            duration = num_frames / sample_rate
            
            # Read audio data
            audio_data = wav_file.readframes(num_frames)
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
            
            if num_channels == 2:
                audio_array = audio_array.reshape(-1, 2)
                left_channel = audio_array[:, 0]
                right_channel = audio_array[:, 1]
                peak_left = np.max(np.abs(left_channel)) / 32767.0
                peak_right = np.max(np.abs(right_channel)) / 32767.0
                peak_overall = max(peak_left, peak_right)
                rms_left = np.sqrt(np.mean(left_channel.astype(np.float64) ** 2)) / 32767.0
                rms_right = np.sqrt(np.mean(right_channel.astype(np.float64) ** 2)) / 32767.0
                rms_overall = (rms_left + rms_right) / 2
            else:
                peak_overall = np.max(np.abs(audio_array)) / 32767.0
                rms_overall = np.sqrt(np.mean(audio_array.astype(np.float64) ** 2)) / 32767.0
            
            # Calculate metrics
            peak_db = 20 * np.log10(peak_overall) if peak_overall > 0 else -np.inf
            rms_db = 20 * np.log10(rms_overall) if rms_overall > 0 else -np.inf
            headroom_db = 0 - peak_db  # dB below 0dBFS
            
            # Check for clipping (values at or near maximum)
            clipping_threshold = 0.99  # 99% of full scale
            if num_channels == 2:
                clipped_samples = np.sum((np.abs(left_channel) >= clipping_threshold * 32767) | 
                                       (np.abs(right_channel) >= clipping_threshold * 32767))
            else:
                clipped_samples = np.sum(np.abs(audio_array) >= clipping_threshold * 32767)
            
            clipping_percentage = (clipped_samples / len(audio_array.flatten())) * 100
            
            return {
                'file_path': file_path,
                'sample_rate': sample_rate,
                'channels': num_channels,
                'duration': duration,
                'peak_level': peak_overall,
                'peak_db': peak_db,
                'rms_level': rms_overall,
                'rms_db': rms_db,
                'headroom_db': headroom_db,
                'clipping_percentage': clipping_percentage,
                'is_clipping': clipping_percentage > 0.1  # More than 0.1% clipping
            }
            
    except Exception as e:
        return {'error': str(e), 'file_path': file_path}

def main():
    parser = argparse.ArgumentParser(description="Analyze audio quality of exported files")
    parser.add_argument("--wav", help="Path to WAV file to analyze")
    parser.add_argument("--all", action="store_true", help="Analyze all audio files in export directory")
    
    args = parser.parse_args()
    
    export_dir = Path("export")
    
    if args.all:
        wav_files = list(export_dir.glob("*.wav"))
        if not wav_files:
            print("No WAV files found in export directory")
            return
        files_to_analyze = wav_files
    elif args.wav:
        files_to_analyze = [Path(args.wav)]
    else:
        # Default: analyze most recent WAV file
        wav_files = list(export_dir.glob("*_audio.wav"))
        if not wav_files:
            print("No audio files found. Run with --help for options.")
            return
        files_to_analyze = [max(wav_files, key=lambda f: f.stat().st_mtime)]
    
    print("🎵 Audio Quality Analysis")
    print("=" * 50)
    
    for file_path in files_to_analyze:
        print(f"\nAnalyzing: {file_path.name}")
        print("-" * 30)
        
        result = analyze_audio_file(file_path)
        
        if 'error' in result:
            print(f"❌ Error: {result['error']}")
            continue
        
        print(f"📊 Basic Info:")
        print(f"   Sample Rate: {result['sample_rate']} Hz")
        print(f"   Channels: {result['channels']}")
        print(f"   Duration: {result['duration']:.2f} seconds")
        
        print(f"\n🔊 Audio Levels:")
        print(f"   Peak Level: {result['peak_level']:.3f} ({result['peak_db']:.1f} dB)")
        print(f"   RMS Level: {result['rms_level']:.3f} ({result['rms_db']:.1f} dB)")
        print(f"   Headroom: {result['headroom_db']:.1f} dB")
        
        print(f"\n🎯 Quality Assessment:")
        if result['is_clipping']:
            print(f"   ❌ CLIPPING DETECTED: {result['clipping_percentage']:.2f}% of samples")
            print("   Audio may sound distorted or harsh")
        else:
            print(f"   ✅ No significant clipping ({result['clipping_percentage']:.3f}%)")
        
        if result['headroom_db'] < 1:
            print("   ⚠️  Very low headroom - audio may sound compressed")
        elif result['headroom_db'] < 3:
            print("   ⚠️  Low headroom - close to clipping")
        elif result['headroom_db'] > 10:
            print("   📢 High headroom - audio could be louder")
        else:
            print("   ✅ Good headroom for clear audio")
        
        if result['peak_db'] > -3:
            print("   ⚠️  Peak level very high - may cause distortion in some players")
        elif result['peak_db'] > -6:
            print("   ✅ Peak level appropriate for digital distribution")
        else:
            print("   📢 Peak level conservative - safe but could be louder")

if __name__ == "__main__":
    main()