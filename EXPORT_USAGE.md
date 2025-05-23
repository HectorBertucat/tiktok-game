# TikTok Battle Game - Export Features

## New Export Capabilities

The TikTok Battle Game now supports multiple modes for video generation with audio!

## Usage Modes

### 1. Export Mode (Recommended for Production)
```bash
python battle.py --export
```
- **Fastest**: Runs at maximum speed without display window
- **Audio Included**: Automatically records and includes all game sound effects
- **Progress Tracking**: Shows export progress every 5 seconds
- **Headless**: No window display, perfect for server deployment

### 2. Watch Mode (Default)
```bash
python battle.py --watch
# or simply
python battle.py
```
- **Interactive**: Watch the game play in real-time
- **Audio Playback**: Hear all sound effects during gameplay  
- **Export**: Still exports video at the end (without recorded audio)
- **Development**: Great for testing and development

### 3. Headless Mode
```bash
python battle.py --headless
```
- **No Display**: Runs without showing the game window
- **Normal Speed**: Runs at normal game speed
- **Silent**: No audio recording

## Features Added

### ✅ Audio Recording & Export
- **Complete Sound Integration**: All game sound effects are recorded during export
- **High Quality Audio**: 44.1kHz WAV recording with automatic mixing
- **Synchronized**: Audio perfectly synced with video timing
- **Automatic Cleanup**: Temporary audio files are automatically removed

### ✅ Headless Export
- **No Window Required**: Export videos without needing to watch the entire game
- **Performance Optimized**: Runs at maximum speed for faster export
- **Server Ready**: Perfect for automated video generation on servers

### ✅ Progress Tracking
- **Export Progress**: Real-time progress updates during export
- **Time Estimates**: Shows current time vs total duration
- **Performance Metrics**: Clear indication of export speed

## Audio Includes

The exported video automatically includes:
- **Combat Sounds**: Hits, blade attacks, collisions
- **Pickup Effects**: Heart collection, shield activation, saw pickup
- **Explosions**: Bomb effects with multiple layers
- **Wall Bounces**: Random bounce sound effects
- **Special Effects**: Power-up sounds and shield blocks

## Export Output

- **Location**: `export/` directory
- **Format**: MP4 with H.264 video and AAC audio
- **Quality**: High-quality 1080x1920 vertical format optimized for TikTok
- **Audio**: Mixed stereo audio with all game sound effects

## Example Workflow

1. **Development & Testing**:
   ```bash
   python battle.py --watch  # Watch and test
   ```

2. **Production Export**:
   ```bash
   python battle.py --export  # Fast export with audio
   ```

3. **Batch Processing**:
   ```bash
   # Generate multiple videos quickly
   python battle.py --export
   # Modify config, then repeat
   ```

## Performance Benefits

- **Export Mode**: ~2-3x faster than watch mode
- **Headless**: No GPU overhead for display
- **Audio Recording**: Minimal performance impact
- **Memory Efficient**: Automatic cleanup of temporary files

The export functionality makes it possible to generate high-quality TikTok videos with complete audio without having to watch the entire battle play out!